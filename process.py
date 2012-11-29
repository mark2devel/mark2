from twisted.internet import protocol, reactor, error
from twisted.application.service import Service
from itertools import chain
import os
import glob
import subprocess


class ProcessProtocol(protocol.ProcessProtocol):
    obuff = ""
    alive = True

    def errReceived(self, data):
        data = data.split("\n")
        data[0] = self.obuff + data[0]
        self.obuff = data.pop()
        for l in data:
            self.dispatch(ServerOutput(line=l))

    def makeConnection(self, transport):
        self.dispatch(ServerStarting(pid=self.transport.pid))

    def processEnded(self, reason):
        self.alive = False
        if isinstance(reason.value, error.ProcessTerminated) and reason.value.exitCode:
            self.dispatch(FatalError, reason = reason.getErrorMessage())
        else:
            self.dispatch(ServerStopped)
            

class Process(Service):
    name = "process"
    protocol = None
    respawn = False

    def __init__(self, parent, jarfile=None):
        self.parent = parent
        self.jarfile = jarfile
        
        reg = self.parent.events.register
        
        reg(self.server_input,    ServerInput)
        
        reg(self.server_start,    ServerStart)
        reg(self.server_started,  ServerOutput, pattern='Done \([\d\.]+s\)\! For help, type "help" or "\?"')
        reg(self.server_stop,     ServerStop)
        reg(self.server_stopping, ServerStopping)
        reg(self.server_stopped,  ServerStopped)

    def build_command(self):
        cmd = []
        cmd.append('java')
        cmd.extend(self.parent.config.get_jvm_options())
        cmd.append('-jar')
        cmd.append(self.find_jar())
        cmd.append('nogui')
        return cmd

    def server_start(self, *e):
        self.protocol = ProcessProtocol()
        self.protocol.dispatch = self.parent.events.dispatch

        cmd = self.build_command()
        self.process = reactor.spawnProcess(self.protocol, cmd[0], cmd)
    
    def server_input(self, e):
        if self.protocol and self.protocol.alive:
            l = e.line
            if not l.endswith('\n'):
                l += '\n'
            self.protocol.transport.write(l)
    
    def server_started(self, e):
        self.parent.events.dispatch(ServerStarted(time=e.match.group(1)))
    
    def server_stop(self, *e):
        k = {}
        if e:
            k = {'reason': e.reason, 'respawn': e.respawn}
            
        if self.protocol.alive:
            self.process.signalProcess('KILL')
            self.parent.events.dispatch(ServerStopping(**k))
    
    def server_stopping(self, e):
        self.respawn = e.respawn
    
    def server_stopped(self, e):
        if self.respawn:
            self.server_start()
            self.respawn = False
    
    def startService(self):
        Service.startService(self)
        self.server_start()

    def stopService(self):
        Service.stopService(self)
        self.server_stop()

#def Process(parent, jarfile=None):
#    service = ProcessService(jarfile)
#    service.setServiceParent(parent)
#    return service.protocol, service

#returns a list of dicts. Each list element is a thread in the process.
def get_usage(pid):
    o = subprocess.check_output(['top', '-bH', '-n', '1', '-p', str(pid)])
    o = [re.findall('[^ ]+', x) for x in o[o.find('\n\n')+2:].split('\n')]
    return [dict(zip(o[0], x)) for x in o[1:-1]]
