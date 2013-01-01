import re

from twisted.internet import protocol, reactor
from twisted.application.service import Service

import events
    
class Top(Service):
    name = "top"
    protocol = None
    transport = None
    cmd = "top -bH -d {interval}.00 -p {pid}"
    
    def __init__(self, parent, interval):
        self.parent = parent
        self.interval = interval
    
    def startService(self): 
        #build the protocol
        self.protocol = protocol.ProcessProtocol()
        self.protocol.outReceived = self.dataReceived
        
        #register a listener
        self.parent.events.register(self.server_starting, events.ServerStarting)
    
    def stopService(self):
        if self.transport:
            self.transport.loseConnection()
        return Service.stopService(self)
    
    def dataReceived(self, data):
        data = data.strip()
        
        #ignore the info at the top
        data = data[data.find('\n\n')+2:]
        
        #split each line
        data = [re.findall('[^\s]+', d) for d in data.split('\n')]
        
        #turn each data line into a dict
        data = [dict(zip(data[0], d)) for d in data[1:]]
        
        #dispatch!
        self.parent.events.dispatch(events.StatThreads(threads=data))
        
    def server_starting(self, event):
        cmd = self.cmd.format(interval=self.interval, pid=event.pid).split(" ")
        
        if self.transport:
            self.transport.loseConnection()
        
        self.transport = reactor.spawnProcess(self.protocol, cmd[0], cmd)
    
