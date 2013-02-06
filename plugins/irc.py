import re

from twisted.words.protocols import irc
from twisted.internet import protocol
from twisted.internet import reactor
from plugins import Plugin
from events import PlayerChat, PlayerJoin, PlayerQuit, ServerOutput, ServerStopping, ServerStopped, ServerStarting, ServerStarted


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
            self.factory.parent.irc_message(user, msg)

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

    #game -> irc settings
    game_columns = True

    game_status_enabled = True
    game_status_left    = "!"
    game_status_right   = " | server {what}."

    game_chat_enabled = True
    game_chat_left    = "{username}"
    game_chat_right   = " | {message}"

    game_join_enabled = True
    game_join_left    = "*"
    game_join_right   = " | --> {username}"

    game_quit_enabled = True
    game_quit_left    = "*"
    game_quit_right   = " | <-- {username}"

    game_server_message_enabled = True
    game_server_message_left    = "#server"
    game_server_message_right   = " | {message}"

    #bukkit only
    game_me_enabled = True
    game_me_left    = "*"
    game_me_right   = " | {username} {message}"

    #irc -> game settings
    irc_chat_enabled = True
    irc_chat_command = "say [IRC] <{nickname}> {message}"

    def setup(self):
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

        if self.game_chat_enabled:
            self.pattern(self.game_chat_left, self.game_chat_right, r'<(?P<username>[A-Za-z0-9_]{1,16})> (?P<message>.+)')

        if self.game_join_enabled:
            self.pattern(self.game_join_left, self.game_join_right, r'(?P<username>[A-Za-z0-9_]{1,16})\[/[\d.:]+\] logged in')

        if self.game_quit_enabled:
            self.pattern(self.game_quit_left, self.game_quit_right, r'(?P<username>[A-Za-z0-9_]{1,16}) lost connection')

        if self.game_server_message_enabled and not (self.irc_chat_enabled and self.irc_chat_command.startswith('say ')):
            self.pattern(self.game_server_message_left, self.game_server_message_right, r'\[(?:Server|SERVER)\] (?P<message>.+)')

        if self.game_me_enabled:
            self.pattern(self.game_me_left, self.game_me_right, r'\* (?P<username>[A-Za-z0-9_]{1,16}) (?P<message>.+)')


    def teardown(self):
        self.factory.reconnect = False
        if self.factory.client:
            self.factory.client.quit("Plugin unloading.")

    def format(self, left, right):
        if self.game_columns:
            left = left.rjust(16)
        return left+right

    def pattern_handler(self, left, right):
        def handler(event,left=left, right=right):
            left  = left.format (*event.match.groups(), **event.match.groupdict())
            right = right.format(*event.match.groups(), **event.match.groupdict())
            self.factory.irc_relay(self.format(left, right))
        return handler

    def pattern(self, left, right, pattern, handler=None):
        def handler(event,left=left, right=right):
            left  = left.format (*event.match.groups(), **event.match.groupdict())
            right = right.format(*event.match.groups(), **event.match.groupdict())
            self.factory.irc_relay(self.format(left, right))
        self.register(handler, ServerOutput, pattern=pattern)

    def handle_starting(self, event):
        self.factory.irc_relay(self.format(self.game_status_left, self.game_status_right.format(what="starting")))

    def handle_stopping(self, event):
        self.factory.irc_relay(self.format(self.game_status_left, self.game_status_right.format(what="stopping")))

    def irc_message(self, user, message):
        if self.irc_chat_enabled:
            self.send(self.irc_chat_command.format(nickname=user, message=message), parseColors=True)
