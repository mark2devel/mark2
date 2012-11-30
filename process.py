from twisted.internet import protocol, reactor, error, defer
from twisted.application.service import Service
from itertools import chain
import os
import glob
import subprocess

import events

class ProcessProtocol(protocol.ProcessProtocol):
    obuff = ""
    alive = True

    def errReceived(self, data):
        data = data.split("\n")
        data[0] = self.obuff + data[0]
        self.obuff = data.pop()
        for l in data:
            self.dispatch(events.ServerOutput(line=l))

    def makeConnection(self, transport):
        self.dispatch(events.ServerStarting(pid=transport.pid))

    def processEnded(self, reason):
        self.alive = False
        if isinstance(reason.value, error.ProcessTerminated) and reason.value.exitCode:
            self.dispatch(events.FatalError(reason = reason.getErrorMessage()))
        else:
            self.dispatch(events.ServerStopped())
            

class Process(Service):
    name = "process"
    protocol = None
    respawn = False
    service_stopping = None

    def __init__(self, parent, jarfile=None):
        self.parent = parent
        self.jarfile = jarfile
        
        reg = self.parent.events.register
        
        reg(self.server_input,    events.ServerInput)
        
        reg(self.server_start,    events.ServerStart)
        reg(self.server_started,  events.ServerOutput, pattern='Done \(([\d\.]+)s\)\! For help, type "help" or "\?"')
        reg(self.server_stop,     events.ServerStop)
        reg(self.server_stopping, events.ServerStopping)
        reg(self.server_stopped,  events.ServerStopped)

    def build_command(self):
        cmd = []
        cmd.append('java')
        cmd.extend(self.parent.config.get_jvm_options())
        cmd.append('-jar')
        cmd.append(self.jarfile)
        cmd.append('nogui')
        return cmd

    def server_start(self, *e):
        self.protocol = ProcessProtocol()
        self.protocol.dispatch = self.parent.events.dispatch
        cmd = self.build_command()
        self.process = reactor.spawnProcess(self.protocol, cmd[0], cmd)
    
    def server_input(self, e):
        if self.protocol and self.protocol.alive and self.protocol.transport:
            l = e.line
            if not l.endswith('\n'):
                l += '\n'
            self.protocol.transport.send(l)
    
    def server_started(self, e):
        self.parent.events.dispatch(events.ServerStarted(time=e.match.group(1)))
    
    def server_stop(self, e=None):
        if e:
            k = {'reason': e.reason, 'respawn': e.respawn}
        else:
            k = {'reason': 'unknown', 'respawn': False}
            
        if self.protocol.alive:
            self.protocol.transport.send('stop')
            self.parent.events.dispatch(events.ServerStopping(**k))
    
    def server_kill(self, e=None):
        self.parent.console("server failed to stop, killing...")
        self.process.signalProcess('KILL')
    
    def server_stopping(self, e):
        self.respawn = e.respawn
    
    def server_stopped(self, e):
        if self.respawn:
            self.server_start()
            self.respawn = False
        elif self.service_stopping:
            self.service_stopping.callback(d)
    
    def startService(self):
        self.server_start()
        return Service.startService(self)

    def stopService(self):
        self.parent.events.dispatch(events.ServerStop(reason="SIGINT", respawn=False))
        self.parent.events.dispatch_delayed(self.server_kill, 60)
        self.service_stopping = defer.Deferred()
        #Service.stopService(self)
        return self.service_stopping

#def Process(parent, jarfile=None):
#    service = ProcessService(jarfile)
#    service.setServiceParent(parent)
#    return service.protocol, service

#returns a list of dicts. Each list element is a thread in the process.
def get_usage(pid):
    o = subprocess.check_output(['top', '-bH', '-n', '1', '-p', str(pid)])
    o = [re.findall('[^ ]+', x) for x in o[o.find('\n\n')+2:].split('\n')]
    return [dict(zip(o[0], x)) for x in o[1:-1]]

def find_jar(search_patterns, hint=None):
    if hint:
        search_patterns.insert(0, hint)
    
    for pattern in search_patterns:
        g = glob.glob(pattern)
        if g:
            return g[0]
    
    return None
