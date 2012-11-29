import re
import os
import traceback
from twisted.internet import reactor
from twisted.application.service import MultiService

#mark2 things
import events
import properties
import user_server
import process

#services
import ping
import query
import snoop

#plugins
import plugins


MARK2_BASE = os.path.dirname(os.path.realpath(__file__))

"""

This is the 'main' class that handles most of the logic

"""


class Manager(MultiService):
    name = "manager"
    stopping = False
    
    def __init__(self, path, initial_output, socketdir, jarfile=None):
        MultiService.__init__(self)
        self.path = path
        self.server_name = os.path.basename(path)
        self.initial_output = initial_output
        self.socketdir = socketdir
        self.jarfile = jarfile
        
        self.f_temp = 'temp.log'
    
    def startService(self):
        MultiService.startService(self)
        """try:
            self.startServiceReal()
        except Exception as e:
            self.fatal_error(exception=e)
        finally:
            #close initial pipe
            if self.initial_output != None:
                os.close(self.initial_output)
                self.initial_output = None"""
        self.startServiceReal()
        #close initial pipe
        if self.initial_output != None:
            os.close(self.initial_output)
            self.initial_output = None
        
    def startServiceReal(self):
        #start event dispatcher
        self.events = events.EventDispatcher()
        
        #add some handlers
        self.events.register(self.handle_commands,      events.Hook, public=True, name="commands", doc="displays this message")
        self.events.register(self.handle_console,       events.Console)
        self.events.register(self.handle_fatal,         events.FatalError)
        self.events.register(self.handle_server_output, events.ServerOutput, level='.*', pattern='.*')
        self.events.register(self.handle_server_stopped,events.ServerStopped)
        self.events.register(self.handle_user_attach,   events.UserAttached)
        self.events.register(self.handle_user_detach,   events.UserDetached)
        self.events.register(self.handle_user_input,    events.UserInput)
        
        #change to server directory
        os.chdir(self.path)
        
        #load config
        self.config = properties.load(os.path.join(MARK2_BASE, 'config', 'mark2.properties'), 'mark2.properties')
        if self.config == None:
            self.fatal(reason="couldn't find mark2.properties")
        
        #load server.properties
        self.properties = properties.load(os.path.join(MARK2_BASE, 'resources', 'server.default.properties'), 'server.properties')
        if self.properties == None:
            self.fatal(reason="couldn't find server.properties")
            
        
        #start services
        if self.config['mark2.service.ping.enabled']:
            self.addService(ping.Ping(
                self,
                self.properties['server-ip'],
                self.properties['query.port'],
                self.config['mark2.service.query.interval'], ))
        
        if self.config['mark2.service.query.enabled'] and self.properties['enable-query']:
            self.addService(query.Query(
                self, 
                self.config['mark2.service.query.interval'], 
                self.properties['server-ip'], 
                self.properties['server-port']))
        
        if self.config['mark2.service.snoop.enabled'] and self.properties['enable-snooper']:
            self.addService(snoop_server.Snoop(
                self, 
                self.config['mark2.service.snoop.interval'], 
                self.jarfile))
        
        self.addService(process.Process(self, self.jarfile))
        self.addService(user_server.UserServer(self, os.path.join(self.socketdir, "%s.sock" % self.name)))
        
        #load plugins
        loaded = []
        
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
        self.console("mark2 started successfully")
    
    
    #helpers
    def console(self, line, **k):
        k['line'] = line
        self.events.dispatch(events.Console(**k))
    
    def fatal_error(self, *a, **k):
        k['reason'] = a[0] if a else None
        self.events.dispatch(events.FatalError(**k))
    
    def send(self, line):
        self.events.dispatch(events.ServerInput(line=line))
    
    #handlers
    def handle_commands(self, event):
        o = []
        m = 0
        for callback, args in self.events.get(events.Hook):
            if args['public']:
                o.append((args['name'], args['doc']))
                m = max(m, len(args['name']))
        
        o = sorted(o, key=lambda x: x[0])
        
        self.console("The following commands are available:")
        for name, doc in o:
            self.console(" ~%s | %s" % (name.ljust(m), doc))
    
    def handle_console(self, event):
        self.f_temp.write("%s\n" % event)
        if self.initial_output:
            os.write(self.initial_output, "%s\n" % event)
    
    def handle_fatal(self, event):
        self.stopping = True
        try:
            service = self.getServiceNamed('process')
            if service.running:
                self.console(event.reason, kind="error")
                self.events.dispatch(events.ServerStop(reason=event.reason))
        except KeyError:
            self.stopService()
    def handle_server_output(self, event):
        result = self.events.dispatch(ServerOutputConsumer(line=event.line))
        if result == 0: #not consumed
            e = Console(
                source = 'server',
                line = event.line,
                time = event.line[:event.line.find(' [')])
                
            self.events.dispatch(e)
    
    def handle_server_stopped(self, event):
        if self.stopping:
            self.stopService()
    

    def handle_user_attach(self, event):
        self.console("%s attached" % event.user, kind="joinpart")
    
    def handle_user_detach(self, event):
        self.console("%s detached" % event.user, kind="joinpart")
    
    def handle_user_input(self, event):
        self.console(event.line, user=event.user, source="user")
        if event.line.startswith("~"):
            t = event.line.split(" ", 1)
            cmd = t[0][1:]
            r = self.events.dispatch(events.Hook(name=cmd, is_command=True, command_args=t[1]))
            if not r & events.ACCEPTED:
                self.console("unknown command.")
        else:
            self.events.dispatch(events.ServerInput(line=event.line))
    
    def handle_command(self, user, text):
        self.console(text, prompt=">", user=user)
        self.send(self.expand_command(user, text))
