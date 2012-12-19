from twisted.internet import protocol, reactor, error, defer
from twisted.application.service import Service
import glob
import subprocess

import events
import re

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
            self.dispatch(events.FatalError(reason=reason.getErrorMessage()))
        else:
            self.dispatch(events.ServerStopped())
            

class Process(Service):
    name = "process"
    protocol = None
    respawn = False
    service_stopping = None
    transport = None
    
    running = False
    
    failsafe = None

    def __init__(self, parent, jarfile=None):
        self.parent = parent
        self.jarfile = jarfile
        
        reg = self.parent.events.register
        
        reg(self.server_input,    events.ServerInput)
        
        reg(self.server_start,    events.ServerStart)
        reg(self.server_started,  events.ServerOutput, pattern='Done \(([0-9\.]+)s\)\! For help, type "help" or "\?"')
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

    def server_start(self, e=None):
        self.parent.console("starting minecraft server")
        self.protocol = ProcessProtocol()
        self.protocol.dispatch = self.parent.events.dispatch
        cmd = self.build_command()
        self.transport = reactor.spawnProcess(self.protocol, cmd[0], cmd)
        if e:
            e.handled = True
        
        self.running = True
    
    def server_input(self, e):
        if self.protocol and self.protocol.alive and self.transport:
            l = e.line
            if not l.endswith('\n'):
                l += '\n'
            self.transport.write(str(l))
            e.handled = True
    
    def server_started(self, e):
        self.parent.events.dispatch(events.ServerStarted(time=e.match.group(1)))
    
    def server_stop(self, *a, **k):
        announce = True
        if len(a) == 1:
            e = a[0]
            e.handled = True
            self.server_stop_real(e.respawn, e.kill, e.reason, e.announce)
        elif k:
            self.server_stop_real(k['respawn'], k['kill'] if 'kill' in k else False, k['reason'], True)
        #TODO: add 'else: raise'. 

    def server_stop_real(self, respawn, kill, reason, announce):
        if kill:
            self.failsafe = None
            self.parent.console("killing minecraft server")
            self.transport.signalProcess('KILL')
            return
        else:
            self.parent.console("stopping minecraft server")
            self.transport.write('stop\n')
            self.failsafe = self.parent.events.dispatch_delayed(events.ServerStop(respawn=respawn, reason=reason, kill=True, announce=False), self.parent.config['mark2.shutdown_timeout'])
        
        if announce:
            self.parent.events.dispatch(events.ServerStopping(respawn=respawn, reason=reason, kill=kill))

    def server_stopping(self, e):
        self.respawn = e.respawn
    
    def server_stopped(self, e):
        if self.failsafe:
            self.failsafe.cancel()
            self.failsafe = None
        self.running = False
        if self.respawn:
            self.server_start()
            self.respawn = False
        elif self.service_stopping:
            self.service_stopping.callback(0)
        else:
            reactor.stop()

    def stopService(self):
        if self.running:
            self.parent.events.dispatch(events.ServerStop(reason="SIGINT", respawn=False))
            self.service_stopping = defer.Deferred()
            return self.service_stopping


def find_jar(search_patterns, hint=None):
    if hint:
        search_patterns.insert(0, hint)
    
    for pattern in search_patterns:
        g = glob.glob(pattern)
        if g:
            return g[0]
    
    return None
