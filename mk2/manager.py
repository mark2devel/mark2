import os
import traceback
import signal

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.python import log, logfile

#mark2 things
from . import events, properties, plugins
from .events import EventPriority
from .services import process
from .shared import find_config, open_resource

"""

This is the 'main' class that handles most of the logic

"""


class Manager(object):
    name = "manager"
    started = False
    shutting_down = False
    
    def __init__(self, shared_path, server_name, server_path, jar_file=None):
        self.shared_path = shared_path
        self.server_name = server_name
        self.server_path = server_path
        self.jar_file = jar_file
        self.players = set()

    def startup(self):
        reactor.addSystemEventTrigger('before', 'shutdown', self.before_reactor_stop)

        try:
            self.really_start()
        except Exception:
            for l in traceback.format_exc().split("\n"):
                print l
                self.console(l, kind='error')
            self.shutdown()

    def before_reactor_stop(self):
        self.console("mark2 stopped.")

    def really_start(self):
        #start event dispatcher
        self.events = events.EventDispatcher(self.handle_dispatch_error)

        #add some handlers
        self.events.register(self.handle_server_output, events.ServerOutput,  priority=EventPriority.MONITOR, pattern="")
        self.events.register(self.handle_console,       events.Console,       priority=EventPriority.MONITOR)
        self.events.register(self.handle_fatal,         events.FatalError,    priority=EventPriority._HIGH)
        self.events.register(self.handle_server_started,events.ServerStarted, priority=EventPriority.MONITOR)
        self.events.register(self.handle_user_attach,   events.UserAttach,    priority=EventPriority.MONITOR)
        self.events.register(self.handle_user_detach,   events.UserDetach,    priority=EventPriority.MONITOR)
        self.events.register(self.handle_user_input,    events.UserInput,     priority=EventPriority.MONITOR)
        self.events.register(self.handle_player_join,   events.PlayerJoin,    priority=EventPriority.MONITOR)
        self.events.register(self.handle_player_quit,   events.PlayerQuit,    priority=EventPriority.MONITOR)
        self.events.register(self.handle_server_stopped,events.ServerStopped, priority=EventPriority.MONITOR)

        #change to server directory
        os.chdir(self.server_path)

        #load config
        self.load_config()

        #start logging
        self.start_logging()

        #chmod log and pid
        for ext in ('log', 'pid'):
            os.chmod(os.path.join(self.shared_path, "%s.%s" % (self.server_name, ext)), self.config.get_umask(ext))

        self.console("mark2 starting...")

        #find jar file
        if self.jar_file is None:
            self.jar_file = process.find_jar(
                self.config['mark2.jar_path'].split(';'),
                self.jar_file)
            if self.jar_file is None:
                return self.fatal_error("Couldn't find server jar!")

        #load server.properties
        self.properties = properties.load(properties.Mark2Properties, open_resource('resources/server.default.properties'), 'server.properties')
        if self.properties is None:
            return self.fatal_error(reason="couldn't find server.properties")

        self.socket = os.path.join(self.shared_path, "%s.sock" % self.server_name)
        
        self.services = plugins.PluginManager(self,
                                              search_path='services',
                                              name='service',
                                              get_config=self.get_service_config)
        for name in self.services.find():
            cfg = self.get_service_config(name)
            if not cfg.get('enabled', True):
                continue
            result = self.services.load(name)
            if not result:
                return self.fatal_error(reason="couldn't load service: '{0}'".format(name))

        #load plugins
        self.plugins = plugins.PluginManager(self,
                                             search_path='plugins',
                                             name='plugin',
                                             get_config=self.get_plugin_config,
                                             require_config=True)
        self.load_plugins()

        #start the server
        self.events.dispatch(events.ServerStart())

    def handle_dispatch_error(self, event, callback, failure):
        o  = "An event handler threw an exception: \n"
        o += "  Callback: %s\n" % callback
        o += "  Event: \n"
        o += "".join(("    %s: %s\n" % (k, v) for k, v in event.serialize().iteritems()))

        # log the message and a very verbose exception log to the log file
        log.msg(o)
        failure.printDetailedTraceback()

        # log a less verbose exception to the console
        o += "\n".join("  %s" % l for l in failure.getTraceback().split("\n"))
        self.console(o)

    #helpers
    def start_logging(self):
        log_rotate = self.config['mark2.log.rotate_mode']
        log_size   = self.config['mark2.log.rotate_size']
        log_limit  = self.config['mark2.log.rotate_limit']
        if log_rotate == 'daily':
            log_obj = logfile.DailyLogFile("%s.log" % self.server_name, self.shared_path)
        elif log_rotate in ('off', 'size'):
            log_obj = logfile.LogFile("%s.log" % self.server_name, self.shared_path,
                                      rotateLength=log_size if log_rotate == 'size' else None,
                                      maxRotatedFiles=log_limit if log_limit != "" else None)
        else:
            raise ValueError("mark2.log.rotate-mode is invalid.")

        log.startLogging(log_obj)

    def load_config(self):
        self.config = properties.load(properties.Mark2Properties,
                                      open_resource('resources/mark2.default.properties'),
                                      find_config('mark2.properties'),
                                      'mark2.properties')
        if self.config is None:
            return self.fatal_error(reason="couldn't find mark2.properties")

    def get_plugin_config(self, name):
        return dict(self.config.get_plugins()).get(name, {})

    def get_service_config(self, name):
        return dict(self.config.get_service(name))

    def load_plugins(self):
        for name, _ in self.config.get_plugins():
            self.plugins.load(name)
    
    def shutdown(self):
        if not self.shutting_down:
            self.shutting_down = True
            reactor.callInThread(lambda: os.kill(os.getpid(), signal.SIGINT))

    def console(self, line, **k):
        for l in unicode(line).split(u"\n"):
            k['line'] = l
            self.events.dispatch(events.Console(**k))
    
    def fatal_error(self, *a, **k):
        k.setdefault('reason', a[0] if a else None)
        self.events.dispatch(events.FatalError(**k))
    
    def send(self, line):
        self.events.dispatch(events.ServerInput(line=line))
            
    #handlers
    def handle_server_output(self, event):
        self.events.dispatch(events.Console(source='server',
                                            line=event.line,
                                            time=event.time,
                                            level=event.level,
                                            data=event.data))

    def handle_console(self, event):
        for line in event.value().encode('utf8').split("\n"):
            log.msg(line, system="mark2")
    
    def handle_fatal(self, event):
        s = "fatal error: %s" % event.reason
        self.console(s, kind="error")
        self.shutdown()

    def handle_server_started(self, event):
        properties_ = properties.load(properties.Mark2Properties, open_resource('resources/server.default.properties'), 'server.properties')
        if properties_:
            self.properties = properties_
        if not self.started:
            self.console("mark2 started.")
            self.started = True

    def handle_user_attach(self, event):
        self.console("%s attached" % event.user, kind="joinpart")
    
    def handle_user_detach(self, event):
        self.console("%s detached" % event.user, kind="joinpart")
    
    @inlineCallbacks
    def handle_user_input(self, event):
        self.console(event.line, user=event.user, source="user")
        if event.line.startswith("~") or event.line.startswith("."):
            handled = yield self.events.dispatch(events.Hook(line=event.line))
            if not handled:
                self.console("unknown command.")
        elif event.line.startswith('#'):
            pass
        else:
            self.events.dispatch(events.ServerInput(line=event.line))
    
    def handle_command(self, user, text):
        self.console(text, prompt=">", user=user)
        self.send(text)

    def handle_player_join(self, event):
        self.players.add(str(event.username))
        self.events.dispatch(events.StatPlayers(players=list(self.players)))

    def handle_player_quit(self, event):
        self.players.discard(str(event.username))
        self.events.dispatch(events.StatPlayers(players=list(self.players)))

    def handle_server_stopped(self, event):
        self.players.clear()
        self.events.dispatch(events.StatPlayers(players=[]))
