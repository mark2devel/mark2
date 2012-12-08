import re
import struct

from twisted.application.internet import TCPClient
from twisted.internet.protocol import Protocol, ReconnectingClientFactory
from twisted.internet import task


class PingProtocol(Protocol):
    def startProtocol(self):
        self.transport.write('\xFE\x01')
    
    def dataReceived(self, data):
        data = data[9:].decode('utf16-be').split('\x00')
        self.dispatch(StatPlayerCount(source="ping", players_current=data[3], players_max=data[4]))

class PingFactory(ReconnectingClientFactory):
    def __init__(self, interval):
        t = task.LoopingCall(self.loop)
        t.start(interval)
    
    def loop(self):
        self.resetDelay()
        self.retry()
    
    def buildProtocol(self, addr):
        pr = PingProtocol()
        pr.dispatch = self.dispatch
        return pr

class Ping(TCPClient):
    name = "ping"
    def __init__(self, parent, host, port, interval):
        factory = PingFactory(interval)
        factory.dispatch = parent.events.dispatch
        TCPClient.__init__(self, host, port, factory)
        
