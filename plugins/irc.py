import re

from twisted.words.protocols import irc
from twisted.internet import protocol
from twisted.internet import reactor
from plugins import Plugin
from events import PlayerChat, PlayerJoin, PlayerQuit, ServerOutput, ServerStopping, ServerStopped, ServerStarting, ServerStarted, StatPlayers


class IRCBot(irc.IRCClient):
    def __init__(self, factory, plugin):
        self.factory     = factory
        self.nickname    = plugin.nickname
        self.realname    = plugin.realname
        self.username    = plugin.username
        self.password    = plugin.password
        self.channel     = plugin.channel
        self.console     = plugin.console
        self.irc_message = plugin.irc_message

    def signedOn(self):
        self.console("irc: connected")
        
        if self.password:
            self.msg('NickServ', 'IDENTIFY %s' % self.password)
        
        self.join(self.channel)

    def joined(self, channel):
        self.console('irc: joined channel')
        self.factory.client = self

    def privmsg(self, user, channel, msg):
        if channel != self.channel:
            return
        m = re.match('([^\!]+)\!.*', user)
        if m:
            user = m.group(1)
            p = self.factory.parent
            if p.irc_players_enabled and msg == p.irc_players_trigger:
                self.say(self.channel, p.irc_players_format.format(players=', '.join(p.players)))
            else:
                p.irc_message(user, msg)

    def alterCollidedNick(self, nickname):
        return nickname+'_'

    def irc_relay(self, message):
        self.say(self.channel, message)


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
    host=None
    port=None
    ssl=False
    channel=None

    #user
    nickname="RelayBot"
    realname="RelayBot"
    username="RelayBot"
    password=""

    #general

    cancel_highlight = False

    #game -> irc settings
    game_columns = True

    game_status_enabled = True
    game_status_format  = "!, | server {what}."

    game_chat_enabled = True
    game_chat_format  = "{username}, | {message}"

    game_join_enabled = True
    game_join_format  = "*, | --> {username}"

    game_quit_enabled = True
    game_quit_format  = "*, | <-- {username}"

    game_server_message_enabled = True
    game_server_message_format  = "#server, | {message}"

    #bukkit only
    game_me_enabled = True
    game_me_format  = "*, | {username} {message}"

    irc_players_enabled = True
    irc_players_trigger = "!players"
    irc_players_format  = "*, | players currently in game: {players}"

    #irc -> game settings
    irc_chat_enabled = True
    irc_chat_command = "say [IRC] <{nickname}> {message}"

    def setup(self):
        self.players = []
        self.factory = IRCBotFactory(self)
        if self.ssl:
            try:
                from twisted.internet import ssl
                reactor.connectSSL(self.host, self.port, self.factory, ssl.ClientContextFactory())
            except ImportError:
                self.parent.fatal_error("Couldn't load SSL for IRC")
        else:
            reactor.connectTCP(self.host, self.port, self.factory)

        if self.game_status_enabled:
            self.register(self.handle_stopping, ServerStopping)
            self.register(self.handle_starting,  ServerStarting)

        def register(event_type, format, *a, **k):
            def handler(event, format):
                if self.game_columns:
                    f = format.split(',', 1)
                    if len(f) == 2:
                        format = f[0].rjust(16) + f[1]
                d = event.match.groupdict() if hasattr(event, 'match') else event.serialize()
                if self.cancel_highlight and 'user' in d:
                    d['user'] = '_' + d['user'][1:]
                line = format.format(**d)
                self.factory.irc_relay(line)
            self.register(lambda e: handler(e, format), event_type, *a, **k)

        if self.game_chat_enabled:
            register(PlayerChat, self.game_chat_format)

        if self.game_join_enabled:
            register(PlayerJoin, self.game_join_format)

        if self.game_quit_enabled:
            register(PlayerQuit, self.game_quit_format)

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


    def handle_starting(self, event):
        self.factory.irc_relay(self.format(self.game_status_left, self.game_status_right.format(what="starting")))

    def handle_stopping(self, event):
        self.factory.irc_relay(self.format(self.game_status_left, self.game_status_right.format(what="stopping")))

    def handle_players(self, event):
        self.players = sorted(event.players)

    def irc_message(self, user, message):
        if self.irc_chat_enabled:
            self.send(self.irc_chat_command.format(nickname=user, message=message), parseColors=True)
