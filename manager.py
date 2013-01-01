import os
import sys
import traceback

from twisted.internet import reactor, defer, error
from twisted.application.service import MultiService, Service
from twisted.python import log

#mark2 things
import signal
import events
import properties
import user_server
import process
from services import ping, query, snoop, top

#plugins
import plugins


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
        self.events = events.EventDispatcher()
        
        #add some handlers
        self.events.register(self.handle_cmd_help,      events.Hook, public=True, name="help", doc="displays this message")
        self.events.register(self.handle_cmd_events,    events.Hook, public=True, name="events", doc="lists events")
        self.events.register(self.handle_console,       events.Console)
        self.events.register(self.handle_fatal,         events.FatalError)
        self.events.register(self.handle_server_save,   events.ServerSave)
        self.events.register(self.handle_server_started,events.ServerStarted)
        self.events.register(self.handle_user_attach,   events.UserAttach)
        self.events.register(self.handle_user_detach,   events.UserDetach)
        self.events.register(self.handle_user_input,    events.UserInput)

        self.console("mark2 starting...")

        #change to server directory
        os.chdir(self.server_path)
        
        #load config
        self.config = properties.load(os.path.join(MARK2_BASE, 'config', 'mark2.properties'), 'mark2.properties')
        if self.config is None:
            return self.fatal_error(reason="couldn't find mark2.properties")
        
        #load server.properties
        self.properties = properties.load(os.path.join(MARK2_BASE, 'resources', 'server.default.properties'), 'server.properties')
        if self.properties is None:
            return self.fatal_error(reason="couldn't find server.properties")
            
        #find jar file
        if self.jar_file is None:
            self.jar_file = process.find_jar(
                self.config['mark2.jar_path'].split(';'),
                self.jar_file)
            if self.jar_file is None:
                return self.fatal_error("Couldn't find server jar!")
                
        #start services
        
        #if using snoop, we need to wait for the jar to be patched
        
        proc_o = process.Process(self, self.jar_file)
        
        def proc_s(x):
            self.addService(proc_o)
        def proc_e(e):
            return self.fatal_error("Failed to patch server jar!")
            
        proc_d = defer.Deferred()
        proc_d.addCallback(proc_s)
        proc_d.addErrback(proc_e)
        
        if self.config['mark2.service.ping.enabled']:
            self.addService(ping.Ping(
                self,
                self.properties['server_ip'],
                self.properties['query.port'],
                self.config['mark2.service.query.interval']))
        
        if self.config['mark2.service.query.enabled'] and self.properties['enable_query']:
            self.addService(query.Query(
                self, 
                self.config['mark2.service.query.interval'], 
                self.properties['server_ip'], 
                self.properties['server_port']))
        
        if self.config['mark2.service.top.enabled']:
            self.addService(top.Top(
                self,
                self.config['mark2.service.top.interval']))
        
        if self.config['mark2.service.snoop.enabled'] and self.properties['snooper_enabled']:
            self.addService(snoop.Snoop(
                self, 
                self.config['mark2.service.snoop.interval']*1000, 
                os.path.abspath(self.jar_file),
                proc_d))
        else:
            proc_d.callback(None)
        
        self.addService(user_server.UserServer(self, os.path.join(self.shared_path, "%s.sock" % self.server_name)))
        
        #load plugins
        loaded = []
        self.plugins = {}
        
        for name, kwargs in self.config.get_plugins():
            try:
                ref = plugins.load(name, **kwargs)
                self.plugins[name] = ref(self, name, **kwargs)
                loaded.append(name)
            except:
                self.console("plugin '%s' failed to load. stack trace follows" % name, kind='error')
                for l in traceback.format_exc().split("\n"):
                    self.console(l, kind='error')
        
        self.console("loaded plugins: " + ", ".join(loaded))
        
        self.events.dispatch(events.ServerStart())
    
    #helpers
    def shutdown(self):
        reactor.callInThread(lambda: os.kill(os.getpid(), signal.SIGINT))

    def console(self, line, **k):
        k['line'] = str(line)
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
    
    def handle_console(self, event):
        for line in str(event).split("\n"):
            log.msg(line, system="mark2")
    
    def handle_fatal(self, event):
        s = "fatal error: %s" % event.reason
        self.console(s, kind="error")
        self.shutdown()
    
    def handle_server_save(self, event):
        self.send('save-all')
        event.handled = True

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
            self.events.dispatch(events.ServerInput(line=event.line))
    
    def handle_command(self, user, text):
        self.console(text, prompt=">", user=user)
        self.send(text)
