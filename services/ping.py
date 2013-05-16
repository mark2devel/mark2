import struct

from twisted.application.service import Service
from twisted.internet import task, reactor
from twisted.internet.protocol import Protocol, ClientFactory

from events import Event, StatPlayerCount, ServerOutput, ServerStarted


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


class Ping(Service):
    name = "ping"
    alive = False
    event_id = None
    
    def __init__(self, parent, interval):
        self.parent = parent

        self.host = self.parent.properties['server_ip'] or '127.0.0.1'

        self.parent.events.register(self.server_started, ServerStarted)

        self.task = task.LoopingCall(self.loop)
        self.task.start(interval, now=False)

    def server_started(self, event):
        if self.event_id:
            self.parent.events.unregister(self.event_id)
        self.event_id = self.parent.events.register(lambda ev: Event.EAT, ServerOutput,
                                                    pattern=r"\s*/%s:\d+ lost connection" % self.host)

    def loop(self):
        host = self.parent.properties['server_ip'] or '127.0.0.1'
        port = self.parent.properties['server_port']

        factory = PingFactory(self.parent.events.dispatch)

        reactor.connectTCP(host, port, factory, bindAddress=(self.host, 0))

    def stopService(self):
        Service.stopService(self)
