from os import path
import imp
import inspect
import re

from twisted.internet import task, reactor

from events import Hook, ServerInput, ServerStarted, ServerStopped

class Plugin:
    _tasks = []
    def __init__(self, parent, name, **kwargs):
        self.parent = parent
        self.name = name
        
        self.config   = self.parent.config
        self.console  = self.parent.console
        self.fatal    = self.parent.fatal
        self.dispatch = self.parent.events.dispatch
        self.register = self.parent.events.register
    
        for n, v in kwargs.iteritems():
            setattr(self, n, v)
        
        self.register(self.server_started, ServerStarted)
        self.register(self.server_stopped, ServerStopped)
        
        self.setup()
    
    def setup(self, event):
        pass
    
    def server_started(self, event):
        pass
    
    def server_stopping(self, event):
        self.stop_tasks()
    
    def delayed_task(self, callback, delay, name=None):
        if name == None:
            name = callback.__func__
        hook = Hook(name=name)
        self.events.register(callback, Hook, name=name)
        t = self.events.dispatch_delayed(hook, delay)
        t._stop = t.cancel
        self._tasks.append(t)
        
    def repeating_task(self, callback, interval, name=None):
        if name == None:
            name = callback.__func__
        hook = Hook(name=name)
        self.events.register(callback, Hook, name=name)
        t = self.events.dispatch_repeating(hook, interval)
        t._stop = t.stop
        self._tasks.append(t)
    
    def stop_tasks(self):
        for t in self._tasks:
            t._stop()
        
    def send(self, l):
        self.dispatch(ServerInput(line=l))
    


def load(module_name, **kwargs):
    print 'load {}'.format(module_name)
    p = path.join(path.dirname(path.realpath(__file__)), module_name + '.py')
    module = imp.load_source(module_name, p)
    classes = inspect.getmembers(module, inspect.isclass)
    for name, cls in classes:
        if issubclass(cls, Plugin) and cls != Plugin:
            return cls
