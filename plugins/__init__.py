from os import path
from glob import glob
import traceback
import imp
import re

from twisted.internet import task, reactor

""" plugin api:

 - register (regex, callback) pairs on server output
 - send commands to server
 - register and call named hooks (plugin.x.y.z)
 - register tasks (name, time, callback)
 - delete tasks by name (del1, delall?)

"""


class Consumer:
    ty = "consumer"
    
    def __init__(self, callback, level, pattern):
        self.callback = callback
        self.regex = re.compile('^(?:\d{4}-\d{2}-\d{2} )?\d{2}:\d{2}:\d{2} \[%s\] %s$' % (level, pattern))
    
    def act(self, line):
        m = self.regex.match(line)
        if not m:
            return False
        
        self.callback(m)
        return True


class Interest(Consumer):
    ty = "interest"


class ConsoleInterest:
    ty = "console_interest"
    
    def __init__(self, callback):
        self.callback = callback
    
    def act(self, line):
        self.callback(line)


class Command:
    ty = "command"
    
    def __init__(self, callback, command, doc=None):
        self.callback = callback
        self.command = command
        self.doc = doc
        if self.doc == None and self.callback.__doc__:
            self.doc = self.callback.__doc__
    
    def __repr__(self):
        o = "  ~%s" % self.command
        if self.doc:
            o += ": %s" % self.doc
        return o
    
    def act(self, user, line):
        self.callback(user, line)


class ShutdownTask:
    ty = "shutdown_task"
    
    def __init__(self, callback):
        self.callback = callback
    
    def act(self, reason):
        self.callback(reason)


class Plugin:
    passed_up = {}
    
    def __init__(self, parent, name, **kwargs):
        self.parent = parent
        self.name = name
        self.pass_up('register')
        self.pass_up('send')
        self.pass_up('kill_process')
        self.pass_up('plugins')
        self.pass_up('console')
        
        for n, v in kwargs.iteritems():
            setattr(self, n, v)
        
        self.setup()
    
    def pass_up(self, *args):
        self.passed_up[args[0]] = args[-1]
    
    def __getattr__(self, name):
        if name in self.passed_up:
            return getattr(self.parent, self.passed_up[name])
        else:
            raise AttributeError
    
    def setup(self):
        pass

    def delayed_task(self, callback, delay):
        t = reactor.callLater(delay, callback)
        return t
    
    def repeating_task(self, callback, interval):
        t = task.LoopingCall(callback)
        t.start(interval, now=False)
        return t


def load(name, **kwargs):
    p = path.join(path.dirname(path.realpath(__file__)), name + '.py')
    module = imp.load_source(name, p)
    return module.ref
        

def get_plugins():
    exp = path.join(path.dirname(path.realpath(__file__)), '*.py')
    for d in glob(exp):
        module_name, ext = path.splitext(path.basename(d))
        if ext == '.py' and not module_name.startswith('_'):
            try:
                module = imp.load_source(module_name, d)
                name = module.name
                plugin = module.ref
                yield name, plugin
            except:
                print 'The plugin "%s" failed to load! Stack trace follows:' % module_name
                traceback.print_exc()
