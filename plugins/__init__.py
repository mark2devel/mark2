from os import path
import imp
import inspect
import re

from twisted.internet import task, reactor
from twisted.internet.error import AlreadyCancelled

from events import Hook, ServerInput, ServerStarted, ServerStopping

class Plugin:
    def __init__(self, parent, name, **kwargs):
        self.parent = parent
        self.name = name
        
        
        self.config             = self.parent.config
        self.console            = self.parent.console
        self.fatal_error        = self.parent.fatal_error
        self.dispatch           = self.parent.events.dispatch
        self.dispatch_delayed   = self.parent.events.dispatch_delayed
        self.dispatch_repeating = self.parent.events.dispatch_repeating
        self.register           = self.parent.events.register
        
        self._tasks = []
    
        for n, v in kwargs.iteritems():
            setattr(self, n, v)
        
        self.register(self.server_started, ServerStarted)
        self.register(self.server_stopping, ServerStopping)
        
        self.setup()
    
    def setup(self):
        pass
    
    def server_started(self, event):
        pass
    
    def server_stopping(self, event):
        self.stop_tasks()
    
    def delayed_task(self, callback, delay, name=None):
        hook = self._task(callback, name)
        t = self.parent.events.dispatch_delayed(hook, delay)
        t._stop = t.cancel
        t._active = t.active
        self._tasks.append(t)

    def repeating_task(self, callback, interval, name=None):
        hook = self._task(callback, name)
        t = self.parent.events.dispatch_repeating(hook, interval)
        t._stop    = t.stop
        t._active = lambda: t.running
        self._tasks.append(t)
    
    def _task(self, callback, name=None):
        if name == None:
            name = id(callback)
        hook = Hook(name=name)
        self.parent.events.register(callback, Hook, name=name)
        return hook

    def stop_tasks(self):
        for t in self._tasks:
            if t._active():
                t._stop()
        self._tasks = []
        
    def send(self, l):
        self.dispatch(ServerInput(line=l))
    


def load(module_name, **kwargs):
    p = path.join(path.dirname(path.realpath(__file__)), module_name + '.py')
    module = imp.load_source(module_name, p)
    classes = inspect.getmembers(module, inspect.isclass)
    for name, cls in classes:
        if issubclass(cls, Plugin) and cls != Plugin:
            return cls
