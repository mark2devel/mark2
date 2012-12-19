import re

from twisted.words.protocols import irc
from twisted.internet import protocol
from twisted.internet import reactor
from plugins import Plugin, Interest


class IRCBot(irc.IRCClient):
    """def connectionMade(self):
        irc.IRCClient.connectionMade(self)

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)"""
        
    in_chan = False

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

    def __init__(self, parent):
        self.parent = parent

    def clientConnectionLost(self, connector, reason):
        print('client connection lost')
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print('client connection failed')
        #reactor.stop()
    
    def buildProtocol(self, addr):
        p = IRCBot()
        p.factory  = self
        p.nickname = self.parent.nickname
        p.realname = self.parent.realname
        p.username = self.parent.username
        p.password = self.parent.password
        p.channel  = self.parent.channel
        p.console  = self.parent.console
        return p
    
    def irc_relay(self, message):
        if self.client:
            self.client.irc_relay(message)

class IRC(Plugin):
    channel = None
    def setup(self):
        if self.game_to_irc_enabled:
            self.register(self.chat_message, ServerOutput, pattern='<([A-Za-z0-9_]{1,16})> (.+)')
        
        self.factory = IRCBotFactory(self)
        
        if self.ssl:
            try:
                from twisted.internet import ssl
                reactor.connectSSL(self.host, self.port, self.factory, ssl.ClientContextFactory())
            except ImportError:
                self.parent.fatal_error("Couldn't load SSL for IRC")
        
        else:
            reactor.connectTCP(self.host, self.port, self.factory)
        

    def chat_message(self, match):
        self.factory.irc_relay(self.game_to_irc_format.format(username=match.group(1), message=match.group(2)))
    
    def irc_message(self, user, message):
        if self.irc_to_game_enabled:
            self.send(self.irc_to_game_command.format(nickname=user, message=message), parseColors=True)
