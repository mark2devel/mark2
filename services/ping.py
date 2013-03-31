import re
import struct

from twisted.application.service import Service
from twisted.internet import task, reactor
from twisted.internet.protocol import Protocol, ClientFactory

from events import StatPlayerCount, ServerOutputConsumer, ACCEPTED


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
                self.dispatch(StatPlayerCount(source="ping", players_current=int(data[3]), players_max=int(data[4])))
                self.transport.loseConnection()


class PingFactory(ClientFactory):
    noisy = False
    
    def __init__(self, interval, host, port, dispatch):
        self.host = host
        self.port = port
        self.dispatch = dispatch
        t = task.LoopingCall(self.loop)
        t.start(interval, now=False)
    
    def loop(self):
        reactor.connectTCP(self.host, self.port, self)
    
    def buildProtocol(self, addr):
        pr = PingProtocol()
        pr.dispatch = self.dispatch
        return pr


class Ping(Service):
    name = "ping"
    
    def __init__(self, parent, host, port, interval):
        h = host if host else '127.0.0.1'
        parent.events.register(self.whine, ServerOutputConsumer, pattern='\/%s\:\d+ lost connection' % re.escape(h))
        
        self.factory = PingFactory(interval, host, port, parent.events.dispatch)
    
    def whine(self, event):
        return ACCEPTED

    def stopService(self):
        self.factory.stopFactory()
        Service.stopService(self)
