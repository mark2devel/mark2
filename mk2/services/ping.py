import struct

from twisted.internet import task, reactor
from twisted.internet.protocol import Protocol, ClientFactory

from mk2.events import Event, StatPlayerCount, ServerOutput
from mk2.plugins import Plugin


class PingProtocol(Protocol):
    def connectionMade(self):
        self.buff = ""
        self.transport.write('\xFE\x01')
    
    def dataReceived(self, data):
        self.buff += data
        if len(self.buff) >= 3:
            l = struct.unpack('>h', self.buff[1:3])[0]
            
            if len(self.buff) >= 3 + l * 2:
                data = self.buff[9:].decode('utf-16be').split('\x00')
                self.dispatch(StatPlayerCount(source='ping', players_current=int(data[3]), players_max=int(data[4])))
                self.transport.loseConnection()


class PingFactory(ClientFactory):
    noisy = False
    
    def __init__(self, dispatch):
        self.dispatch = dispatch
    
    def buildProtocol(self, addr):
        pr = PingProtocol()
        pr.dispatch = self.dispatch
        return pr


class Ping(Plugin):
    alive = False
    event_id = None

    interval = Plugin.Property(default=10)
    
    def setup(self):
        self.host = self.parent.properties['server_ip'] or '127.0.0.1'

        self.task = task.LoopingCall(self.loop)
        self.task.start(self.interval, now=False)

    def server_started(self, event):
        if self.event_id:
            self.parent.events.unregister(self.event_id)
        pattern = r"\s*(?:/{0}:\d+ lost connection|Reached end of stream for /{0})"
        self.event_id = self.parent.events.register(lambda ev: Event.EAT, ServerOutput,
                                                    pattern=pattern.format(self.host))

    def loop(self):
        host = self.parent.properties['server_ip'] or '127.0.0.1'
        port = self.parent.properties['server_port']

        factory = PingFactory(self.parent.events.dispatch)

        reactor.connectTCP(host, port, factory, bindAddress=(self.host, 0))
