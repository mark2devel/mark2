import locale
from twisted.internet import protocol, reactor, error, defer, task
import glob
import psutil
import shlex


from mk2 import events
from mk2.events import EventPriority
from mk2.plugins import Plugin


class ProcessProtocol(protocol.ProcessProtocol):
    obuff = ""
    alive = True

    def __init__(self, dispatch, locale):
        self.dispatch = dispatch
        self.locale = locale

    def output(self, line):
        self.dispatch(events.ServerOutput(line=line))

    def childDataReceived(self, fd, data):
        if data[0] == '\b':
            data = data.lstrip(' \b')
        if type(data) == bytes:
            data = data.decode(self.locale)
        data = data.split("\n")
        data[0] = self.obuff + data[0]
        self.obuff = data.pop()
        for l in data:
            self.output(l.strip('\r'))

    def makeConnection(self, transport):
        self.dispatch(events.ServerStarting(pid=transport.pid))

    def processEnded(self, reason):
        self.alive = False
        if isinstance(reason.value, error.ProcessTerminated) and reason.value.exitCode:
            self.dispatch(events.ServerEvent(cause='server/error/exit-failure',
                                             data="server exited abnormally: {}".format(reason.getErrorMessage()),
                                             priority=1))
            self.dispatch(events.FatalError(reason=reason.getErrorMessage()))
        else:
            self.dispatch(events.ServerStopped())


class Process(Plugin):
    name = "process"
    protocol = None
    respawn = False
    service_stopping = None
    transport = None
    failsafe = None
    stat_process = None
    done_pattern = Plugin.Property(default='Done \(([0-9\.]+)s\)!.*')
    stop_cmd = Plugin.Property(default='stop\n')
    java_path = Plugin.Property(default='java')
    server_args = Plugin.Property(default='')

    def setup(self):
        self.register(self.server_input,    events.ServerInput,    priority=EventPriority.MONITOR)
        self.register(self.server_start,    events.ServerStart,    priority=EventPriority.MONITOR)
        self.register(self.server_starting, events.ServerStarting)
        self.register(self._server_started, events.ServerOutput,   pattern=self.done_pattern)
        self.register(self.server_stop,     events.ServerStop,     priority=EventPriority.MONITOR)
        self.register(self.server_stopping, events.ServerStopping, priority=EventPriority.MONITOR)
        self.register(self.server_stopped,  events.ServerStopped,  priority=EventPriority.MONITOR)

        reactor.addSystemEventTrigger('before', 'shutdown', self.before_reactor_stop)

    def build_command(self):
        cmd = []
        cmd.append(self.java_path)
        cmd.extend(self.parent.config.get_jvm_options())
        cmd.append('-jar')
        cmd.append(self.parent.jar_file)
        cmd.append('nogui')
        cmd.extend(shlex.split(self.server_args))
        return cmd

    def server_start(self, e=None):
        # make sure the server is actually not running
        if self.protocol and self.protocol.alive:
            self.console("skipping start event as the server is already running")
        else:
            self.parent.console("starting %s" % self.parent.server_name)
            self.locale = locale.getpreferredencoding()
            self.protocol = ProcessProtocol(self.parent.events.dispatch, self.locale)
            cmd = self.build_command()
    
            self.transport = reactor.spawnProcess(self.protocol, cmd[0], cmd, env=None)
        
        if e:
            e.handled = True

    def server_input(self, e):
        if self.protocol and self.protocol.alive:
            l = e.line
            if not l.endswith('\n'):
                l += '\n'
            self.transport.write(l.encode(self.locale, 'ignore'))
            e.handled = True

    def server_starting(self, e):
        self.stat_process = task.LoopingCall(self.update_stat, psutil.Process(e.pid))
        self.stat_process.start(self.parent.config['java.ps.interval'])
        self.parent.console("jar file: %s" % self.parent.jar_file)
        self.parent.console("pid: %s" % e.pid)
        self.parent.console("jvm options: %s" % ' '.join(self.parent.config.get_jvm_options()))

    def _server_started(self, e):
        self.parent.events.dispatch(events.ServerStarted())

    @defer.inlineCallbacks
    def server_stop(self, e):
        e.handled = True
        if self.protocol is None or not self.protocol.alive:
            if e.respawn == events.ServerStop.TERMINATE:
                print("I'm stopping the reactor now! Reason: {}".format(e.reason))
                reactor.stop()
                return
            else:
                self.parent.console("server is not running")
                return
        if e.announce:
            yield self.parent.events.dispatch(events.ServerStopping(respawn=e.respawn, reason=e.reason, kill=e.kill))
        
        
        if self.failsafe and self.failsafe.active():
            self.failsafe.cancel()
            self.failsafe = None
        if e.kill:
            self.failsafe = None
            self.parent.console("killing %s (caused by %s)" % (self.parent.server_name,e.reason))
            self.transport.signalProcess('KILL')
        else:
            self.parent.console("stopping %s (caused by %s)" % (self.parent.server_name,e.reason))
            self.transport.write(self.stop_cmd.encode(self.locale))
            self.failsafe = self.parent.events.dispatch_delayed(events.ServerStop(respawn=e.respawn, reason=e.reason, kill=True, announce=False), self.parent.config['mark2.shutdown_timeout'])

    def server_stopping(self, e):
        self.respawn = e.respawn

    def server_stopped(self, e):
        if self.stat_process and self.stat_process.running:
            self.stat_process.stop()
        if self.failsafe and self.failsafe.active():
            self.failsafe.cancel()
            self.failsafe = None
        if self.respawn == events.ServerStop.RESTART:
            self.parent.events.dispatch(events.ServerStart())
            self.respawn = events.ServerStop.TERMINATE
        elif self.respawn == events.ServerStop.HOLD:
            self.respawn = events.ServerStop.TERMINATE
            return
        elif self.service_stopping:
            self.service_stopping.callback(0)
        else:
            print("I'm stopping the reactor now")
            reactor.stop()

    def update_stat(self, process):
        try:
            self.parent.events.dispatch(events.StatProcess(cpu=process.cpu_percent(interval=0), memory=process.memory_percent()))
        except psutil.NoSuchProcess:
            pass

    def before_reactor_stop(self):
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
