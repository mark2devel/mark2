import os
import traceback

import process
import plugins
import aserver
import properties
import query
import re

from twisted.internet import reactor
from twisted.application.service import MultiService

RESOURCE_BASE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

"""

This is the 'main' class that handles most of the logic

"""


class Manager(MultiService):
    
    protocol = None
    process = None
    resurrect = False
    failure = None
    query = None
    players = []
    
    ###
    ### Useful things
    ###
    
    def __init__(self, path, output, socketdir, jarfile=None):
        MultiService.__init__(self)
        self.path = path
        self.name = os.path.basename(path)
        self.clients = {}
        self.console_log = []
        self.output = output
        self.socketdir = socketdir
        self.jarfile = jarfile
    
    def startService(self):
        MultiService.startService(self)
        
        #Change to server directory
        if not (os.path.exists(self.path) and os.path.isdir(self.path)):
            self.fatal_error("couldn't find specificed path: %s" % self.path)
        
        os.chdir(self.path)
        
        #Set up /tmp folder
        if not os.path.isdir(self.socketdir):
            os.mkdir(self.socketdir)
        
        self.socket = os.path.join(self.socketdir, "%s.sock" % self.name)
        
        self.reset_registers()
        
        try:
            self.load_profile()
            self.load_plugins()
            self.start_process()
            self.start_terminal()
        except Exception as e:
            self.fatal_error(str(e), exception=e)
        
        self.startup_output("Server started successfully at {}".format(self.socket))
        
        os.close(self.output)
        self.output = 0
    
    def startup_output(self, line):
        if not self.output:
            return
        os.write(self.output, '{}\n'.format(line))
    
    def load_profile(self):
        p = properties.Properties(os.path.join(RESOURCE_BASE, 'mark2.default.properties'))
        if os.path.exists('mark2.properties'):
            p = properties.Properties('mark2.properties', p)
        
        self.cfg = p
        
        if self.cfg['havent_read_conf']:
            self.fatal_error("Read your configuration file, then try again. (hint: havent_read_conf)")
    
    def fatal_error(self, message, exception=None):
        self.startup_output("[ERROR] {}".format(message))
        if exception:
            raise exception
        else:
            self.shutdown('fatal_error', message)
    
    def server_started(self, match):
        p = properties.Properties(os.path.join(RESOURCE_BASE, 'server.default.properties'))
        p = properties.Properties('server.properties', p)
        self.server_properties = p
        
        if not self.query and self.server_properties['enable-query']:
            self.query = query.Query(self, self.query_callback, self.server_properties['server-ip'], self.server_properties['query.port'])
    
    def query_callback(self, d):
        self.players = d['players']
    
    def shutdown(self, caller, reason='(no reason)'):
        if self.output:
            os.close(self.output)
        raise Exception("shutdown() called for {}: {}".format(caller, reason))
    
    ###
    ### process
    ###
    
    def kill_process(self):
        self.console('Stopping service: {}'.format(self.process))
        self.process.stopService()
    
    def start_process(self):
        self.protocol, self.process = process.Process(self, self.jarfile)
    
    #Called when the server process gives us a line
    def p_out(self, data):
        consumed = -1
        for i, consumer in enumerate(self.consumers):
            r = consumer.act(data)
            if r:
                consumed = i
                break
        
        if consumed == -1:
            errors = re.match('^(?:\d{4}-\d{2}-\d{2} )?\d{2}:\d{2}:\d{2} \[(?:ERROR|WARNING)\] .*$', data)
            self.console(data, prompt="|", kind='error' if errors else None)
        else:
            self.consumers.pop(i)
        
        for interest in self.interests:
            interest.act(data)
    
    #Send data to the server
    def p_in(self, data):
        if self.protocol:
            self.protocol.transport.write(str(data))
    
    #Called when the process stops
    def p_stop(self):
        for task in self.shutdown_tasks:
            task.act(self.failure)
        if self.resurrect:
            self.start_process()
            self.resurrect = False
        else:
            reactor.stop()
    
    ###
    ### terminal
    ###
    
    def start_terminal(self):
        self.aserver = aserver.AServer(self)
    
    def handle_attach(self, protocol, user, lines):
        self.console('%s attached' % user, prompt="#", kind='joinpart')
        self.clients[user] = protocol
        
        protocol.send_helper('options',
                             format=self.cfg.get_format_options(),
                             prompt=self.cfg.get('mark2.client.prompt', '%'))
        
        self.update_userlist()
        
        for l in self.console_log[-lines:]:
            protocol.send_output(*l)
    
    def handle_detach(self, user):
        if user in self.clients:
            self.console('%s detached' % user, prompt="#", kind='joinpart')
            del self.clients[user]
            
            self.update_userlist()
    
    def update_userlist(self):
        for name, user in self.clients.items():
            user.send_helper('userlist', users=self.clients.keys())
    
    def handle_chat(self, user, text):
        self.console("#" + text, prompt='>', user=user)
    
    def handle_plugin(self, user, text):
        self.console("~" + text, prompt='>', user=user)
        
        t = text.split(" ", 1)
        cmd = t[0]
        
        if cmd in self.commands:
            self.commands[cmd].act(user, t[1] if len(t) == 2 else "")
        else:
            self.console("unknown command.")
    
    def expand_command(self, user, text):
        return self.cfg['mark2.command_format'].format(user=user, command=text)
    
    def handle_command(self, user, text):
        self.console(text, prompt=">", user=user)
        self.send(self.expand_command(user, text))

    def console(self, text, prompt="#", user="", kind=None):
        w = 10
        user = user.rjust(w) if len(user) < w else user[-w:]
        line = "{user} {prompt} {text}".format(user=user, prompt=prompt, text=text)
        
        self.console_log.append((line, kind))
        for proto in self.clients.values():
            proto.send_output(line, kind)
        for console_interest in self.console_interests:
            console_interest.act(line)
    
    ###
    ### plugin
    ###

    def reset_registers(self):
        self.plugins   = {}
        self.interests = []
        self.consumers = []
        self.shutdown_tasks = []
        self.commands  = {}
        self.console_interests = []
        self.register(plugins.Interest(self.server_started, 'INFO', 'Done \([\d\.]+s\)\! For help, type "help" or "\?"'))
        self.register(plugins.Command(self.plugin_commands, 'commands', 'displays this message'))
    
    def plugin_commands(self, *a):
        o = []
        m = 0
        for name, command in sorted(self.commands.items(), key=lambda m: m[0]):
            o.append((name, command.doc))
            m = max(m, len(name))
        
        self.console("The following commands are available:")
        for name, doc in o:
            self.console("  ~%s | %s" % (name.ljust(m), doc))
      
    def load_plugins(self):
        pl = self.cfg.get_plugins()
        #m = max([len(n) for n, a in pl])
        loaded = []
        
        for name, kwargs in pl:
            try:
                ref = plugins.load(name, **kwargs)
                self.plugins[name] = ref(self, name, **kwargs)
                loaded.append(name)
            except:
                self.console("plugin '%s' failed to load. stack trace follows" % name, kind='error')
                for l in traceback.format_exc().split("\n"):
                    self.console(l, kind='error')
        
        self.console("loaded plugins: " + ", ".join(loaded))
    
    def register(self, thing):
        if thing.ty == "interest":
            self.interests.append(thing)
        if thing.ty == "consumer":
            self.consumers.append(thing)
        if thing.ty == "command":
            self.commands[thing.command] = thing
        if thing.ty == "shutdown_task":
            self.shutdown_tasks.append(thing)
        if thing.ty == "console_interest":
            self.console_interests.append(thing)
    
    def send(self, text):
        #print text
        self.p_in(text + "\n")
