from twisted.internet import protocol, reactor, error, defer
from twisted.application.service import Service
from itertools import chain
import os
import glob
import subprocess

import events

from twisted.python import log

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
        if len(a)==1:
            e = a[0]
            e.handled = True
            self.server_stop_real(e.respawn, e.kill, e.reason, e.announce)
        elif k:
            self.server_stop_real(k['respawn'], k['kill'] if 'kill' in k else False, k['reason'], True)
        #TODO: add 'else: raise'. 

    def server_stop_real(self, respawn, kill, reason, announce):
        if kill:
            self.parent.console("killing minecraft server")
            self.transport.signalProcess('KILL')
            return
        elif not kill:
            self.parent.console("stopping minecraft server")
            self.transport.write('stop\n')
            self.parent.events.dispatch_delayed(events.ServerStop(respawn=respawn, reason=reason, kill=True, announce=False), self.parent.config['mark2.shutdown_timeout'])
        else:
            raise Exception("process has no way of dealing with ServerStop...")
        
        if announce:
            self.parent.events.dispatch(events.ServerStopping(respawn=respawn, reason=reason, kill=kill))

    def server_stopping(self, e):
        self.respawn = e.respawn
    
    def server_stopped(self, e):
        if self.respawn:
            self.server_start()
            self.respawn = False
        elif self.service_stopping:
            self.parent.console("minecraft server has stopped!")
            self.service_stopping.callback(0)

    def stopService(self):
        self.parent.events.dispatch(events.ServerStop(reason="SIGINT", respawn=False))
        self.service_stopping = defer.Deferred()
        return self.service_stopping

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
