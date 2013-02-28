import locale
from twisted.internet import protocol, reactor, error, defer
from twisted.application.service import Service
import glob
import pwd
import events

class ProcessProtocol(protocol.ProcessProtocol):
    obuff = u""
    alive = True

    def __init__(self, dispatch, locale):
        self.dispatch = dispatch
        self.locale = locale

    def output(self, line):
        event_1 = events.ServerOutputConsumer(line=line)
        consumed = self.dispatch(event_1)
        if not consumed:
            event_2 = events.Console(source='server', line=event_1.line, time=event_1.time, level=event_1.level, data=event_1.data)
            self.dispatch(event_2)
            event_3 = events.ServerOutput(line=line)
            self.dispatch(event_3)

    def errReceived(self, data):
        data = data.decode(self.locale)
        data = data.split("\n")
        data[0] = self.obuff + data[0]
        self.obuff = data.pop()
        for l in data:
            self.output(l)

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
    failsafe = None

    def __init__(self, parent, jarfile=None):
        self.parent = parent
        self.jarfile = jarfile

        reg = self.parent.events.register

        reg(self.server_input,    events.ServerInput)
        reg(self.server_start,    events.ServerStart)
        reg(self.server_started,  events.ServerOutput, pattern='Done \\(([0-9\\.]+)s\\)\\!.*')
        reg(self.server_stop,     events.ServerStop)
        reg(self.server_stopping, events.ServerStopping)
        reg(self.server_stopped,  events.ServerStopped)

    def build_command(self):
        cmd = []
        cmd.append('java')
        #cmd.append('-server')
        cmd.extend(self.parent.config.get_jvm_options())
        cmd.append('-jar')
        cmd.append(self.jarfile)
        cmd.append('nogui')
        return cmd

    def server_start(self, e=None):
        self.parent.console("starting minecraft server")
        self.locale = locale.getpreferredencoding()
        self.protocol = ProcessProtocol(self.parent.events.dispatch, self.locale)
        cmd = self.build_command()

        uid = None
        gid = None
        user = self.parent.config['java.user']
        if user != '':
            try:
                d = pwd.getpwnam(user)
                uid = d.pw_uid
                gid = d.pw_gid
            except KeyError:
                pass

        self.transport = reactor.spawnProcess(self.protocol, cmd[0], cmd, env=None, uid=uid, gid=gid)
        if e:
            e.handled = True

    def server_input(self, e):
        if self.protocol and self.protocol.alive:
            l = e.line
            if not l.endswith('\n'):
                l += '\n'
            self.transport.write(l.encode(self.locale))
            e.handled = True

    def server_started(self, e):
        self.parent.events.dispatch(events.ServerStarted(time=e.match.group(1)))

    def server_stop(self, e):
        e.handled = True
        if self.protocol is None or not self.protocol.alive:
            return
        if e.announce:
            self.parent.events.dispatch(events.ServerStopping(respawn=e.respawn, reason=e.reason, kill=e.kill))
        if e.kill:
            self.failsafe = None
            self.parent.console("killing minecraft server")
            self.transport.signalProcess('KILL')
        else:
            self.parent.console("stopping minecraft server")
            self.transport.write('stop\n')
            self.failsafe = self.parent.events.dispatch_delayed(events.ServerStop(respawn=e.respawn, reason=e.reason, kill=True, announce=False), self.parent.config['mark2.shutdown_timeout'])

    def server_stopping(self, e):
        self.respawn = e.respawn

    def server_stopped(self, e):
        if self.failsafe:
            self.failsafe.cancel()
            self.failsafe = None
        if self.respawn:
            self.server_start()
            self.respawn = False
        elif self.service_stopping:
            self.service_stopping.callback(0)
        else:
            reactor.stop()

    def stopService(self):
        if self.protocol and self.protocol.alive:
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