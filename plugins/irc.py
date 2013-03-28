import re
import os.path as path

from twisted.words.protocols import irc
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.python.util import InsensitiveDict
from plugins import Plugin
from events import PlayerChat, PlayerJoin, PlayerQuit, PlayerDeath, ServerOutput, ServerStopping, ServerStarting, StatPlayers

try:
    from OpenSSL import SSL
    from twisted.internet import ssl
    from twisted.protocols.tls import TLSMemoryBIOProtocol

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


class IRCBot(irc.IRCClient):
    def __init__(self, factory, plugin):
        self.factory     = factory
        self.nickname    = plugin.nickname.encode('ascii')
        self.realname    = plugin.realname.encode('ascii')
        self.username    = plugin.username.encode('ascii')
        self.ns_password = plugin.password
        self.password    = plugin.server_password.encode('ascii')
        self.channel     = plugin.channel.encode('ascii')
        self.console     = plugin.console
        self.irc_message = plugin.irc_message
        self.users       = InsensitiveDict()

    def signedOn(self):
        if have_ssl and isinstance(self.transport, TLSMemoryBIOProtocol):
            cert = self.transport.getPeerCertificate()
            fp = cert.digest("sha1")
            verified = "verified" if self.factory.parent.server_fingerprint else "unverified"
            self.console("irc: connected securely. server fingerprint: {} ({})".format(fp, verified))
        else:
            self.console("irc: connected")
        
        if self.ns_password:
            self.msg('NickServ', 'IDENTIFY %s' % self.ns_password)
        
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
        
        if p.irc_chat_status and p.irc_chat_status in self.priority:
            priority = self.priority[p.irc_chat_status]
            u = self.users.get(nick, None)
            if not u or u.priority is None or u.priority > priority:
                return
        if p.irc_players_enabled and msg == p.irc_players_trigger:
            self.say(self.channel, p.irc_players_format.format(players=', '.join(p.players)))
        else:
            p.irc_message(nick, msg)

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
    host = None
    port = None
    server_password = ""
    channel = None
    certificate = None
    ssl = False
    server_fingerprint = None

    #user
    nickname = "RelayBot"
    realname = "RelayBot"
    username = "RelayBot"
    password = ""

    #general
    cancel_highlight = False
    cancel_highlight_str = u"_"

    #game -> irc settings
    game_columns = True

    game_status_enabled = True
    game_status_format  = u"!, | server {what}."

    game_chat_enabled = True
    game_chat_format  = u"{username}, | {message}"
    game_chat_private = None

    game_join_enabled = True
    game_join_format  = u"*, | --> {username}"

    game_quit_enabled = True
    game_quit_format  = u"*, | <-- {username}"

    game_death_enabled = True
    game_death_format = u"*, | {text}"

    game_server_message_enabled = True
    game_server_message_format  = u"#server, | {message}"

    #bukkit only
    game_me_enabled = True
    game_me_format  = u"*, | {username} {message}"

    irc_players_enabled = True
    irc_players_trigger = u"!players"
    irc_players_format  = u"*, | players currently in game: {players}"

    #irc -> game settings
    irc_chat_enabled = True
    irc_chat_command = u"say [IRC] <{nickname}> {message}"
    irc_chat_status = None

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
            register(PlayerDeath, self.game_death_format)

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
