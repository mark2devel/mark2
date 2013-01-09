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
        self.parent.console("irc: lost connection with server: %s" % reason)
        if self.reconnect:
            self.parent.console("irc: reconnecting...")
            connector.connect()

    def clientConnectionFailed(self, connector, reason):
        self.parent.console("irc: connection attempt failed: %s" % reason)
    
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

    #settings
    game_to_irc_enabled=True
    game_to_irc_format="<{username}> {message}"
    server_message_format="[Server] {message}"
    status_message_format="* ({message})"
    irc_to_game_enabled=False
    irc_to_game_command="say [IRC] <{nickname}> {message}"

    def setup(self):
        if self.game_to_irc_enabled:
            self.pattern(self.game_to_irc_format,    r'<(?P<username>[A-Za-z0-9_]{1,16})> (?P<message>.+)')
            self.pattern(self.server_message_format, r'\[(?:Server|SERVER)\] (?P<message>.+)')
            self.pattern('{} connected',             r'(?P<username>[A-Za-z0-9_]{1,16})\[/[\d.:]+\] logged in')
            self.pattern('{} disconnected',          r'(?P<username>[A-Za-z0-9_]{1,16}) lost connection')
            self.pattern('* {} {}',                  r'\* (?P<username>[A-Za-z0-9_]{1,16}) (?P<message>.+)')
            # cocks
            self.register(self.handle_shutdown, ServerStopping)
        
        if self.restore:
            self.factory = self.restore
            if self.factory.client:
                self.factory.client.setNick(self.nickname)
                self.factory.irc_relay(self.status_message_format.format(message="Plugin reloaded"))
            return
        
        self.factory = IRCBotFactory(self)
        
        if self.ssl:
            try:
                from twisted.internet import ssl
                reactor.connectSSL(self.host, self.port, self.factory, ssl.ClientContextFactory())
            except ImportError:
                self.parent.fatal_error("Couldn't load SSL for IRC")
        
        else:
            reactor.connectTCP(self.host, self.port, self.factory)
    
    def pattern(self, format, pattern):
        def handler(event):
            self.factory.irc_relay(format.format(*event.match.groups(), **event.match.groupdict()))
        self.register(handler, ServerOutput, pattern=pattern)
    
    def has_cfg_changed(self):
        keys = ['host', 'port', 'ssl', 'channel', 'realname', 'username', 'password']
        pl = dict(self.parent.config.get_plugins())
        if 'irc' not in pl: return True
        pl = pl['irc']
        for k in keys:
            if getattr(self, k) != pl.get(k, None): return True
        return False
    
    def unloading(self, reason="reloading"):
        if self.has_cfg_changed():
            self.factory.reconnect = False
            if self.factory.client:
                self.factory.client.quit("Plugin " + reason)
        else:
            return self.factory
    
    def handle_shutdown(self, event):
        self.factory.irc_relay(self.status_message_format.format(message="Server " + ("restarting" if event.respawn else "stopping")))
    
    def chat_message(self, event):
        match = event.match
        self.factory.irc_relay(self.game_to_irc_format.format(username=match.group(1), message=match.group(2)))
    
    def irc_message(self, user, message):
        if self.irc_to_game_enabled:
            self.send(self.irc_to_game_command.format(nickname=user, message=message), parseColors=True)
