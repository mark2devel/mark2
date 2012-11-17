import os
import sys
import re
import traceback

import process
import plugins
import aserver
import properties
import query

from twisted.internet import protocol, reactor

SOCKET_BASE   = '/tmp/mcpitch/'
RESOURCE_BASE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

"""

This is the 'main' class that handles most of the logic

"""

class Manager:
    
    protocol = None
    process = None
    resurrect = False
    failure = None
    query = None
    players = []
    
    ###
    ### Useful things
    ###
    
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.clients = {}
        self.console_log = []
        
        #Change to server directory
        if not (os.path.exists(self.path) and os.path.isdir(self.path)):
            self.fatal_error("couldn't find specificed path: %s" % self.path)
        
        os.chdir(self.path)
        
        #Set up /tmp folder
        if not os.path.isdir(SOCKET_BASE):
            os.mkdir(SOCKET_BASE)
        
        self.socket = os.path.join(SOCKET_BASE, "%s.sock" % self.name)
        
        self.reset_registers()
        self.load_profile()
        self.load_plugins()
        self.start_process()
        self.start_terminal()
    
    def load_profile(self):
        p = properties.Properties(os.path.join(RESOURCE_BASE, 'mark2.default.properties'))
        if os.path.exists('mark2.properties'):
            p = properties.Properties('mark2.properties', p)
        
        self.cfg = p

    def run_forever(self):
        reactor.run()

    def fatal_error(self, message):
        print "[ERROR] %s" % message
        self.shutdown()
    
    def server_started(self, match):
        p = properties.Properties(os.path.join(RESOURCE_BASE, 'server.default.properties'))
        p = properties.Properties('server.properties', p)
        self.server_properties = p
        
        if not self.query and self.server_properties['enable-query']:
            self.query = query.Query(self.query_callback, self.server_properties['server-ip'], self.server_properties['query.port'])
        
        #self.handle_plugin("bg6g09", "~stop-warn")
    
    def query_callback(self, d):
        self.players = d['players']
        #pass
    
    def plugin_commands(self, *a):
        
        o = []
        m = 0
        for name, command in sorted(self.commands.items(), key=lambda m: m[0]):
            o.append((name, command.doc))
            m = max(m, len(name))
        
        
        self.console("The following commands are available:")
        for name, doc in o:
            self.console("  ~%s | %s" % (name.ljust(m), doc))
    
    
    def shutdown(self):
        #self.process.shutdown()
        print "shutdown completed!"
        sys.exit(1)
    
    ###
    ### process
    ###
    
    
    def kill_process(self):
        self.protocol.transport.signalProcess('KILL')
    
    def start_process(self):
        self.protocol, self.process = process.Process(self)
    
    #Called when the server process gives us a line
    def p_out(self, data):
        consumed = -1
        for i, consumer in enumerate(self.consumers):
            r = consumer.act(data)
            if r:
                consumed = i
                break
        
        if consumed == -1:
            self.console(data, prompt="|")
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
        self.console('%s attached' % user, prompt="#")
        self.clients[user] = protocol
        for l in self.console_log[-lines:]:
            protocol.send_output(l)
        
        self.update_userlist()
    
    def handle_detach(self, user):
        #TODO: check this code over
        if user in self.clients:
            self.console('%s detached' % user, prompt="#")
            #p = self.clients[user]
            #p.stop() #TODO
            del self.clients[user]
            
            self.update_userlist()
    
    def update_userlist(self):
        for name, user in self.clients.items():
            user.send_helper('userlist', users=self.clients.keys())
    
    def handle_chat(self, user, text):
        self.console("#"+text, prompt='>', user=user)
    
    def handle_plugin(self, user, text):
        self.console("~"+text, prompt='>', user=user)
        
        t = text.split(" ", 1)
        cmd = t[0]
        
        if cmd in self.commands:
            self.commands[cmd].act(user, t[1] if len(t)==2 else "")
        else:
            self.console("unknown command.")
    
    def handle_command(self, user, text):
        self.console(text, prompt=">", user=user)
        self.send(text)

    def console(self, text, prompt="#", user=""):
        w = 10
        user = user.rjust(w) if len(user) < w else user[-w:]
        line = "{user} {prompt} {text}".format(user=user, prompt=prompt, text=text)
        
        print line
        
        self.console_log.append(line)
        for proto in self.clients.values():
            proto.send_output(line)
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
      
    def load_plugins(self):
       
        pl = self.cfg.get_plugins()
        m = max([len(n) for n, a in pl])
        loaded = []
        
        for name, kwargs in pl:
            try:
                ref = plugins.load(name, **kwargs)
                self.plugins[name] = ref(self, name, **kwargs)
                loaded.append(name)
            except:
                self.console("plugin '%s' failed to load. stack trace follows" % name)
                for l in traceback.format_exc().split("\n"):
                    self.console(l)
        
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
        self.p_in(text+"\n")

def main():
    m = Manager('/home/ed/mark2/testserver')
    try:
        m.run_forever()
    except KeyboardInterrupt:
        m.shutdown()
        
if __name__ == '__main__':
    main()
