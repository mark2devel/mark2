import re
import os.path as path

from twisted.words.protocols import irc
from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet.interfaces import ISSLTransport
from twisted.python.util import InsensitiveDict

from mk2.plugins import Plugin
from mk2.events import PlayerChat, PlayerJoin, PlayerQuit, PlayerDeath, ServerOutput, ServerStopping, ServerStarting, StatPlayers, Hook

try:
    from OpenSSL import SSL
    from twisted.internet import ssl

    have_ssl = True
    
    class Mark2ClientContextFactory(ssl.ClientContextFactory):
        def __init__(self, parent, fingerprint=None, cert=None):
            self.parent = parent
            self.fingerprint = fingerprint
            self.cert = path.expanduser(cert) if cert else None
        
        @staticmethod
        def stripfp(fp):
            return fp.replace(':', '').lower()
        
        def verify(self, conn, cert, errno, errdepth, rc):
            ok = self.stripfp(cert.digest("sha1")) == self.stripfp(self.fingerprint)
            if self.parent and self.parent.factory.reconnect and not ok:
                self.parent.console("irc: server certificate verification failed")
                self.parent.factory.reconnect = False
            return ok
            
        def getContext(self):
            ctx = ssl.ClientContextFactory.getContext(self)
            if self.fingerprint:
                ctx.set_verify(SSL.VERIFY_PEER, self.verify)
            if self.cert:
                ctx.use_certificate_file(self.cert)
                ctx.use_privatekey_file(self.cert)
            return ctx
except:
    have_ssl = False


class IRCUser(object):
    username = ""
    hostname = ""
    status = ""
    oper = False
    away = False
    
    def __init__(self, parent, nick):
        self.parent = parent
        self.nick = nick
    
    @property
    def priority(self):
        p = self.parent.priority
        if self.status:
            return min([p[s] for s in self.status])
        else:
            return None


class SASLExternal(object):
    name = "EXTERNAL"

    def __init__(self, username, password):
        pass

    def is_valid(self):
        return True

    def respond(self, data):
        return ""


class SASLPlain(object):
    name = "PLAIN"

    def __init__(self, username, password):
        self.response = "{0}\0{0}\0{1}".format(username, password)

    def is_valid(self):
        return self.response != "\0\0"

    def respond(self, data):
        if data:
            return False
        return self.response


SASL_MECHANISMS = (SASLExternal, SASLPlain)


class IRCBot(irc.IRCClient):
    sasl_buffer = ""
    sasl_result = None
    sasl_login = None

    def __init__(self, factory, plugin):
        self.factory     = factory
        self.nickname    = plugin.nickname.encode('ascii')
        self.realname    = plugin.realname.encode('ascii')
        self.username    = plugin.ident.encode('ascii')
        self.ns_username = plugin.username
        self.ns_password = plugin.password
        self.password    = plugin.server_password.encode('ascii')
        self.channel     = plugin.channel.encode('ascii')
        self.console     = plugin.console
        self.irc_message = plugin.irc_message

        self.users       = InsensitiveDict()
        self.cap_requests = set()

    def register(self, nickname, hostname="foo", servername="bar"):
        self.sendLine("CAP LS")
        return irc.IRCClient.register(self, nickname, hostname, servername)

    def _parse_cap(self, cap):
        mod = ''
        while cap[0] in "-~=":
            mod, cap = mod + cap[0], cap[1:]
        if '/' in cap:
            vendor, cap = cap.split('/', 1)
        else:
            vendor = None
        return (cap, mod, vendor)

    def request_cap(self, *caps):
        self.cap_requests |= set(caps)
        self.sendLine("CAP REQ :{0}".format(' '.join(caps)))

    @defer.inlineCallbacks
    def end_cap(self):
        if self.sasl_result:
            yield self.sasl_result
        self.sendLine("CAP END")

    def irc_CAP(self, prefix, params):
        self.supports_cap = True
        identifier, subcommand, args = params
        args = args.split(' ')
        if subcommand == "LS":
            self.sasl_start(args)
            if not self.cap_requests:
                self.sendLine("CAP END")
        elif subcommand == "ACK":
            ack = []
            for cap in args:
                if not cap:
                    continue
                cap, mod, vendor = self._parse_cap(cap)
                if '-' in mod:
                    if cap in self.capabilities:
                        del self.capabilities[cap]
                    continue
                self.cap_requests.remove(cap)
                if cap == 'sasl':
                    self.sasl_next()
            if ack:
                self.sendLine("CAP ACK :{0}".format(' '.join(ack)))
            if not self.cap_requests:
                self.end_cap()
        elif subcommand == "NAK":
            # this implementation is probably not compliant but it will have to do for now
            for cap in args:
                self.cap_requests.remove(cap)
            if not self.cap_requests:
                self.end_cap()

    def signedOn(self):
        if ISSLTransport.providedBy(self.transport):
            cert = self.transport.getPeerCertificate()
            fp = cert.digest("sha1")
            verified = "verified" if self.factory.parent.server_fingerprint else "unverified"
            self.console("irc: connected securely. server fingerprint: {0} ({1})".format(fp, verified))
        else:
            self.console("irc: connected")
        
        if self.ns_username and self.ns_password and not self.sasl_login:
            self.msg('NickServ', 'IDENTIFY {0} {1}'.format(self.ns_username, self.ns_password))
        
        self.join(self.channel)

    def irc_JOIN(self, prefix, params):
        nick = prefix.split('!')[0]
        channel = params[-1]
        if nick == self.nickname:
            self.joined(channel)
        else:
            self.userJoined(prefix, channel)

    def joined(self, channel):
        self.console('irc: joined channel')
        self.factory.client = self
        def who(a):
            self.sendLine("WHO " + channel)
        self.factory.parent.repeating_task(who, 30, now=True)
    
    def isupport(self, args):
        self.compute_prefix_names()
        
    def compute_prefix_names(self):
        KNOWN_NAMES = {"o": "op", "h": "halfop", "v": "voice"}
        prefixdata = self.supported.getFeature("PREFIX", {"o": ("@", 0), "v": ("+", 1)}).items()
        op_priority = ([priority for mode, (prefix, priority) in prefixdata if mode == "o"] + [None])[0]
        self.prefixes, self.statuses, self.priority = {}, {}, {}

        for mode, (prefix, priority) in prefixdata:
            name = "?"
            if mode in KNOWN_NAMES:
                name = KNOWN_NAMES[mode]
            elif priority == 0:
                if op_priority == 2:
                    name = "owner"
                else:
                    name = "admin"
            else:
                name = "+" + mode
            self.prefixes[mode] = prefix
            self.statuses[prefix] = name
            self.priority[name] = priority
            self.priority[mode] = priority
            self.priority[prefix] = priority

    def parse_prefixes(self, user, nick, prefixes=''):
        status = []
        prefixdata = self.supported.getFeature("PREFIX", {"o": ("@", 0), "v": ("+", 1)}).items()
        for mode, (prefix, priority) in prefixdata:
            if prefix in prefixes + nick:
                nick = nick.replace(prefix, '')
                status.append((prefix, priority))
        if nick == self.nickname:
            return
        user.status = ''.join(t[0] for t in sorted(status, key=lambda t: t[1]))
    
    def irc_RPL_WHOREPLY(self, prefix, params):
        _, channel, username, host, server, nick, status, hg = params
        if nick == self.nickname:
            return
        hops, gecos = hg.split(' ', 1)
        user = IRCUser(self, nick)
        user.username = username
        user.hostname = host
        user.oper = '*' in status
        user.away = status[0] == 'G'
        self.users[nick] = user
        self.parse_prefixes(user, nick, status[1:].replace('*', ''))
    
    def modeChanged(self, user, channel, _set, modes, args):
        args = list(args)
        if channel.lower() != self.channel.lower():
            return
        for m, arg in zip(modes, args):
            if m in self.prefixes and arg != self.nickname:
                u = self.users.get(arg, None)
                if u:
                    u.status = u.status.replace(self.prefixes[m], '')
                    if _set:
                        u.status = ''.join(sorted(list(u.status + self.prefixes[m]),
                                                  key=lambda k: self.priority[k]))

    def has_status(self, nick, status):
        if status != 0 and not status:
            return True
        if status not in self.priority:
            return False
        priority = self.priority[status]
        u = self.users.get(nick, None)
        return u and (u.priority is not None) and u.priority <= priority
    
    def userJoined(self, user, channel):
        nick = user.split('!')[0]
        user = IRCUser(self, nick)
        self.users[nick] = user
    
    def userRenamed(self, oldname, newname):
        if oldname not in self.users:
            return
        u = self.users[oldname]
        u.nick = newname
        self.users[newname] = u
        del self.users[oldname]
    
    def userLeft(self, user, channel):
        if user not in self.users:
            return
        del self.users[user]
    
    def userKicked(self, kickee, channel, kicker, message):
        if kickee not in self.users:
            return
        del self.users[kickee]
    
    def userQuit(self, user, quitMessage):
        if user not in self.users:
            return
        del self.users[user]

    def privmsg(self, user, channel, msg):
        if channel != self.channel:
            return
        if '!' not in user:
            return
        nick = user.split('!')[0]
        p = self.factory.parent
        
        if not self.has_status(nick, p.irc_chat_status):
            return

        if p.irc_players_enabled and msg.lower() == p.irc_command_prefix + "players":
            self.say(self.channel, p.irc_players_format.format(players=', '.join(p.players)))

        elif p.irc_command_prefix and msg.startswith(p.irc_command_prefix) and p.irc_command_status and self.has_status(nick, p.irc_command_status):
            argv = msg[len(p.irc_command_prefix):].split(' ')
            command = argv[0]
            if command.startswith('~'):
                if p.irc_command_mark2 and (command.lower() in p.irc_command_allow.lower().split(',') or p.irc_command_allow == '*'):
                    p.dispatch(Hook(line=' '.join(argv)))
            else:
                if command.lower() in p.irc_command_allow.lower().split(',') or p.irc_command_allow == '*':
                    p.send(' '.join(argv))

        else:
            p.irc_message(nick, msg)

    def irc_AUTHENTICATE(self, prefix, params):
        self.sasl_continue(params[0])

    def sasl_send(self, data):
        while data and len(data) >= 400:
            en, data = data[:400].encode('base64').replace('\n', ''), data[400:]
            self.sendLine("AUTHENTICATE " + en)
        if data:
            self.sendLine("AUTHENTICATE " + data.encode('base64').replace('\n', ''))
        else:
            self.sendLine("AUTHENTICATE +")

    def sasl_start(self, cap_list):
        if 'sasl' not in cap_list:
            print cap_list
            return
        self.request_cap('sasl')
        self.sasl_result = defer.Deferred()
        self.sasl_mechanisms = list(SASL_MECHANISMS)

    def sasl_next(self):
        mech = None
        while not mech or not mech.is_valid():
            if not self.sasl_mechanisms:
                return False
            self.sasl_auth = mech = self.sasl_mechanisms.pop(0)(self.ns_username, self.ns_password)
        self.sendLine("AUTHENTICATE " + self.sasl_auth.name)
        return True

    def sasl_continue(self, data):
        if data == '+':
            data = ''
        else:
            data = data.decode('base64')
        if len(data) == 400:
            self.sasl_buffer += data
        else:
            response = self.sasl_auth.respond(self.sasl_buffer + data)
            if response is False:  # abort
                self.sendLine("AUTHENTICATE *")
            else:
                self.sasl_send(response)
            self.sasl_buffer = ""

    def sasl_finish(self):
        if self.sasl_result:
            self.sasl_result.callback(True)
            self.sasl_result = None

    def sasl_failed(self, whine=True):
        if self.sasl_login is False:
            return
        if self.sasl_next():
            return
        self.sasl_login = False
        self.sendLine("AUTHENTICATE *")
        self.sasl_finish()
        if whine:
            self.console("irc: failed to log in.")

    def irc_904(self, prefix, params):
        print params
        self.sasl_failed()

    def irc_905(self, prefix, params):
        print params
        self.sasl_failed()

    def irc_906(self, prefix, params):
        self.sasl_failed(False)

    def irc_907(self, prefix, params):
        self.sasl_failed(False)

    def irc_900(self, prefix, params):
        self.sasl_login = params[2]
        self.console("irc: logged in as '{0}' (using {1})".format(self.sasl_login, self.sasl_auth.name))

    def irc_903(self, prefix, params):
        self.sasl_finish()

    def alterCollidedNick(self, nickname):
        return nickname + '_'

    def irc_relay(self, message):
        self.say(self.channel, message.encode('utf8'))


class IRCBotFactory(protocol.ClientFactory):
    protocol = IRCBot
    client = None
    reconnect = True

    def __init__(self, parent):
        self.parent = parent

    def clientConnectionLost(self, connector, reason):
        if self.reconnect:
            self.parent.console("irc: lost connection with server: %s" % reason.getErrorMessage())
            self.parent.console("irc: reconnecting...")
            connector.connect()

    def clientConnectionFailed(self, connector, reason):
        self.parent.console("irc: connection attempt failed: %s" % reason.getErrorMessage())
    
    def buildProtocol(self, addr):
        p = IRCBot(self, self.parent)
        return p
    
    def irc_relay(self, message):
        if self.client:
            self.client.irc_relay(message)


class IRC(Plugin):
    #connection
    host               = Plugin.Property(required=True)
    port               = Plugin.Property(required=True)
    server_password    = Plugin.Property()
    channel            = Plugin.Property(required=True)
    certificate        = Plugin.Property()
    ssl                = Plugin.Property(default=False)
    server_fingerprint = Plugin.Property()

    #user
    nickname = Plugin.Property(default="RelayBot")
    realname = Plugin.Property(default="mark2 IRC relay")
    ident    = Plugin.Property(default="RelayBot")
    username = Plugin.Property(default="")
    password = Plugin.Property(default="")

    #general
    cancel_highlight     = Plugin.Property(default=False)
    cancel_highlight_str = Plugin.Property(default=u"_")

    #game -> irc settings
    game_columns = Plugin.Property(default=True)

    game_status_enabled = Plugin.Property(default=True)
    game_status_format  = Plugin.Property(default=u"!, | server {what}.")

    game_chat_enabled = Plugin.Property(default=True)
    game_chat_format  = Plugin.Property(default=u"{username}, | {message}")
    game_chat_private = Plugin.Property(default=None)

    game_join_enabled = Plugin.Property(default=True)
    game_join_format  = Plugin.Property(default=u"*, | --> {username}")

    game_quit_enabled = Plugin.Property(default=True)
    game_quit_format  = Plugin.Property(default=u"*, | <-- {username}")

    game_death_enabled = Plugin.Property(default=True)
    game_death_format  = Plugin.Property(default=u"*, | {text}")

    game_server_message_enabled = Plugin.Property(default=True)
    game_server_message_format  = Plugin.Property(default=u"#server, | {message}")

    #bukkit only
    game_me_enabled = Plugin.Property(default=True)
    game_me_format  = Plugin.Property(default=u"*, | {username} {message}")

    #irc -> game settings
    irc_chat_enabled    = Plugin.Property(default=True)
    irc_chat_command    = Plugin.Property(default=u"say [IRC] <{nickname}> {message}")
    irc_chat_status     = Plugin.Property(default=None)

    irc_command_prefix  = Plugin.Property(default="!")
    irc_command_status  = Plugin.Property(default=None)
    irc_command_allow   = Plugin.Property(default="")
    irc_command_mark2   = Plugin.Property(default=False)

    irc_players_enabled = Plugin.Property(default=True)
    irc_players_format  = Plugin.Property(default=u"*, | players currently in game: {players}")

    def setup(self):
        self.players = []
        self.factory = IRCBotFactory(self)
        if self.ssl:
            if have_ssl:
                cf = Mark2ClientContextFactory(self,
                                               cert=self.certificate,
                                               fingerprint=self.server_fingerprint)
                reactor.connectSSL(self.host, self.port, self.factory, cf)
            else:
                self.parent.console("Couldn't load SSL for IRC!")
                return
        else:
            reactor.connectTCP(self.host, self.port, self.factory)

        if self.game_status_enabled:
            self.register(self.handle_stopping, ServerStopping)
            self.register(self.handle_starting,  ServerStarting)
        
        self.column_width = 16
        if self.cancel_highlight == "insert":
            self.column_width += len(self.cancel_highlight_str)

        def register(event_type, format, filter_=None, *a, **k):
            def handler(event, format):
                d = event.match.groupdict() if hasattr(event, 'match') else event.serialize()
                if filter_ and 'message' in d:
                    if filter_.match(d['message']):
                        return
                if self.cancel_highlight and 'username' in d and d['username'] in self.factory.client.users:
                    d['username'] = self.mangle_username(d['username'])
                line = self.format(format, **d)
                self.factory.irc_relay(line)
            self.register(lambda e: handler(e, format), event_type, *a, **k)

        if self.game_chat_enabled:
            if self.game_chat_private:
                try:
                    filter_ = re.compile(self.game_chat_private)
                    register(PlayerChat, self.game_chat_format, filter_=filter_)
                except:
                    self.console("plugin.irc.game_chat_private must be a valid regex")
                    register(PlayerChat, self.game_chat_format)
            else:
                register(PlayerChat, self.game_chat_format)

        if self.game_join_enabled:
            register(PlayerJoin, self.game_join_format)

        if self.game_quit_enabled:
            register(PlayerQuit, self.game_quit_format)

        if self.game_death_enabled:
            def handler(event):
                d = event.serialize()
                for k in 'username', 'killer':
                    if k in d and d[k] and d[k] in self.factory.client.users:
                        d[k] = self.mangle_username(d[k])
                text = event.get_text(**d)
                line = self.format(self.game_death_format, text=text)
                self.factory.irc_relay(line)
            self.register(handler, PlayerDeath)

        if self.game_server_message_enabled and not (self.irc_chat_enabled and self.irc_chat_command.startswith('say ')):
            register(ServerOutput, self.game_server_message_format, pattern=r'\[(?:Server|SERVER)\] (?P<message>.+)')

        if self.game_me_enabled:
            register(ServerOutput, self.game_me_format, pattern=r'\* (?P<username>[A-Za-z0-9_]{1,16}) (?P<message>.+)')

        if self.irc_chat_enabled:
            self.register(self.handle_players, StatPlayers)

    def teardown(self):
        self.factory.reconnect = False
        if self.factory.client:
            self.factory.client.quit("Plugin unloading.")
        
    def mangle_username(self, username):
        if self.cancel_highlight == False:
            return username
        elif self.cancel_highlight == "insert":
            return username[:-1] + self.cancel_highlight_str + username[-1:]
        else:
            return self.cancel_highlight_str + username[1:]

    def format(self, format, **data):
        if self.game_columns:
            f = unicode(format).split(',', 1)
            f[0] = f[0].format(**data)
            if len(f) == 2:
                f[0] = f[0].rjust(self.column_width)
                f[1] = f[1].format(**data)
            return ''.join(f)
        else:
            return format.format(**data)

    def handle_starting(self, event):
        self.factory.irc_relay(self.format(self.game_status_format, what="starting"))

    def handle_stopping(self, event):
        self.factory.irc_relay(self.format(self.game_status_format, what="stopping"))

    def handle_players(self, event):
        self.players = sorted(event.players)

    def irc_message(self, user, message):
        if self.irc_chat_enabled:
            self.send_format(self.irc_chat_command, parseColors=True, nickname=user, message=message)
