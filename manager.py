import os
import traceback
import signal

from twisted.internet import reactor, defer, error
from twisted.application.service import MultiService, Service
from twisted.python import log, logfile

#mark2 things
import events
import properties
import user_server
import process
import plugins
from services import ping, query


MARK2_BASE = os.path.dirname(os.path.realpath(__file__))

"""

This is the 'main' class that handles most of the logic

"""


class Manager(MultiService):
    name = "manager"
    started = False
    
    def __init__(self, shared_path, server_name, server_path, jar_file=None):
        MultiService.__init__(self)
        self.shared_path = shared_path
        self.server_name = server_name
        self.server_path = server_path
        self.jar_file = jar_file
        self.players = set()

    def startService(self):
        Service.startService(self)
        try:
            self.startServiceReal()
        except Exception:
            for l in traceback.format_exc().split("\n"):
                self.console(l, kind='error')
            self.shutdown()

    def stopService(self):
        def finish_up(d):
            self.console("mark2 stopped.")

        d = MultiService.stopService(self)
        d.addCallback(finish_up)
        return d

    def startServiceReal(self):
        #start event dispatcher
        self.events = events.EventDispatcher(self.handle_dispatch_error)

        #add some handlers
        self.events.register(self.handle_cmd_help,          events.Hook, public=True, name="help", doc="displays this message")
        self.events.register(self.handle_cmd_events,        events.Hook, public=True, name="events", doc="lists events")
        self.events.register(self.handle_cmd_plugins,       events.Hook, public=True, name="plugins", doc="lists running plugins")
        self.events.register(self.handle_cmd_reload_plugin, events.Hook, public=True, name="reload-plugin", doc="reload a plugin")
        self.events.register(self.handle_cmd_reload,        events.Hook, public=True, name="reload", doc="reload config and all plugins")
        self.events.register(self.handle_cmd_jar,           events.Hook, public=True, name="jar", doc="wrap a different server jar")

        self.events.register(self.handle_console,       events.Console)
        self.events.register(self.handle_fatal,         events.FatalError)
        self.events.register(self.handle_server_started,events.ServerStarted)
        self.events.register(self.handle_user_attach,   events.UserAttach)
        self.events.register(self.handle_user_detach,   events.UserDetach)
        self.events.register(self.handle_user_input,    events.UserInput)
        self.events.register(self.handle_player_join,   events.PlayerJoin)
        self.events.register(self.handle_player_quit,   events.PlayerQuit)
        self.events.register(self.handle_server_stopped,events.ServerStopped)

        #change to server directory
        os.chdir(self.server_path)

        #load config
        self.config = properties.load(properties.Mark2Properties,
            os.path.join(MARK2_BASE, 'resources', 'mark2.default.properties'),
            os.path.join(MARK2_BASE, 'config', 'mark2.properties'),
            'mark2.properties')
        if self.config is None:
            return self.fatal_error(reason="couldn't find mark2.properties")

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

        #load lang
        self.lang = properties.load_jar(self.jar_file, 'lang/en_US.lang')
        if self.lang is None:
            return self.fatal_error(reason="couldn't load lang!")
        for name, pattern in self.lang.get_deaths():
            self.events.register(lambda e, cause=name: self.events.dispatch(events.PlayerDeath(text=e.data, cause=cause, **e.match.groupdict())), events.ServerOutput, pattern=pattern)

        #load server.properties
        self.properties = properties.load(properties.Mark2Properties, os.path.join(MARK2_BASE, 'resources', 'server.default.properties'), 'server.properties')
        if self.properties is None:
            return self.fatal_error(reason="couldn't find server.properties")

        #register chat handlers
        for key, e_ty in (
            ('join', events.PlayerJoin),
            ('quit', events.PlayerQuit),
            ('chat', events.PlayerChat)):
            self.events.register(lambda e, e_ty=e_ty: self.events.dispatch(e_ty(**e.match.groupdict())), events.ServerOutput, pattern=self.config['mark2.regex.'+key])

        #start services
        if self.config['mark2.service.ping.enabled']:
            self.addService(ping.Ping(
                self,
                self.properties['server_ip'],
                self.properties['server_port'],
                self.config['mark2.service.query.interval']))

        if self.config['mark2.service.query.enabled'] and self.properties['enable_query']:
            self.addService(query.Query(
                self,
                self.config['mark2.service.query.interval'],
                self.properties['server_ip'],
                self.properties['query.port']))

        self.process = process.Process(self, self.jar_file)
        self.addService(self.process)
        self.addService(user_server.UserServer(self, os.path.join(self.shared_path, "%s.sock" % self.server_name)))

        #load plugins
        self.plugins = plugins.PluginManager(self)
        self.load_plugins()

        #start the server
        self.events.dispatch(events.ServerStart())

    def handle_dispatch_error(self, event, callback, exception):
        o  = "An event handler threw an exception: \n"
        o += "  Callback: %s\n" % callback
        o += "  Event: \n"
        o += "".join(("    %s: %s\n" % (k, v) for k, v in event.serialize().iteritems()))
        o += "\n".join("  %s" % l for l in traceback.format_exc().split("\n"))
        log.msg(o)
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
                                      rotateLength = log_size if log_rotate == 'size' else None,
                                      maxRotatedFiles = log_limit if log_limit != "" else None)
        else:
            raise ValueError("mark2.log.rotate-mode is invalid.")

        log.startLogging(log_obj)
        #remove /dev/null logger
        log.theLogPublisher.observers.pop(0)

    def load_plugins(self):
        self.config = properties.load(properties.Mark2Properties, os.path.join(MARK2_BASE, 'config', 'mark2.properties'), 'mark2.properties')
        self.plugins.config = self.config
        self.plugins.load_all()
    
    def shutdown(self):
        reactor.callInThread(lambda: os.kill(os.getpid(), signal.SIGINT))

    def console(self, line, **k):
        for l in unicode(line).split(u"\n"):
            k['line'] = l
            self.events.dispatch(events.Console(**k))
    
    def fatal_error(self, *a, **k):
        k['reason'] = a[0] if a else None
        self.events.dispatch(events.FatalError(**k))
    
    def send(self, line):
        self.events.dispatch(events.ServerInput(line=line))
    
    def table(self, v):
        m = 0
        for name, doc in v:
            m = max(m, len(name))
        
        for name, doc in sorted(v, key=lambda x: x[0]):
            self.console(" ~%s | %s" % (name.ljust(m), doc))
            
    #handlers
    def handle_cmd_help(self, event):
        o = []
        for callback, args in self.events.get(events.Hook):
            if args.get('public', False):
                o.append((args['name'], args.get('doc', '')))
        
        self.console("The following commands are available:")
        self.table(o)
    
    def handle_cmd_events(self, event):
        self.console("The following events are available:")
        self.table([(n, c.doc) for n, c in events.get_all()])

    def handle_cmd_plugins(self, events):
        self.console("These plugins are running: " + ", ".join(sorted(self.plugins.keys())))

    def handle_cmd_reload_plugin(self, event):
        if event.args in self.plugins:
            self.plugins.reload(event.args)
            self.console("%s reloaded." % event.args)
        else:
            self.console("unknown plugin.")

    def handle_cmd_reload(self, event):
        self.plugins.unload_all()
        self.load_plugins()
        self.console("config + plugins reloaded.")

    def handle_cmd_jar(self, event):
        new_jar = process.find_jar(
            self.config['mark2.jar_path'].split(';'),
            event.args)
        if new_jar:
            self.console("I will switch to {} at the next restart".format(new_jar))
            self.jar_file = self.process.jarfile = new_jar
        else:
            self.console("Can't find a matching jar file.")

    def handle_console(self, event):
        for line in event.value().encode('utf8').split("\n"):
            log.msg(line, system="mark2")
    
    def handle_fatal(self, event):
        s = "fatal error: %s" % event.reason
        self.console(s, kind="error")
        self.shutdown()

    def handle_server_started(self, event):
        if not self.started:
            self.console("mark2 started.")
            self.started = True

    def handle_user_attach(self, event):
        self.console("%s attached" % event.user, kind="joinpart")
    
    def handle_user_detach(self, event):
        self.console("%s detached" % event.user, kind="joinpart")
    
    def handle_user_input(self, event):
        self.console(event.line, user=event.user, source="user")
        if event.line.startswith("~"):
            r = self.events.dispatch(events.Hook(line = event.line))
            if not r & events.ACCEPTED:
                self.console("unknown command.")
        elif event.line.startswith('#'):
            pass
        else:
            self.events.dispatch(events.ServerInput(line=event.line, parse_colors=True))
    
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