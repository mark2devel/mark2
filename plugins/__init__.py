# -*- coding: utf-8 -*-
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
        
        self.restore = None
        
        self._tasks = []
        self._events = []
        self._services = []
    
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
    
    def register(self, callback, event_type, **args):
        self._events.append((callback, event_type, args))
        self.parent.events.register(callback, event_type, **args)
    
    def unregister_events(self):
        for callback, event_type, args in self._events:
            self.parent.events.unregister(callback, event_type, **args)
    
    def unloading(self, reason):
        pass
    
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
        
    def send(self, l, parseColors=False):
        if parseColors:
            l = l.replace('&', '\xa7')
        self.dispatch(ServerInput(line=l))
    
    def action_chain(self, spec, callbackWarn, callbackAction):
        intervals = [self.parse_time(i) for i in spec.split(';')]
        intervals = sorted(intervals, key=lambda a: a[1])
        
        def action_chain_i(i_name, i_delay, i_action):
            reactor.callLater(i_delay, i_action) 
            callbackWarn(i_name)
        
        lastAction = callbackAction
        lastTime   = 0
        totalTime  = 0
        
        for name, time in intervals:
            delay = time-lastTime
            lastAction = lambda name=name,delay=delay,lastAction=lastAction: action_chain_i(name, delay, lastAction)
            lastTime   = time
            totalTime += time
        
        return totalTime, lastAction

    def parse_time(self, spec):
        symbols = {'s': (1, 'second'), 'm': (60, 'minute'), 'h': (3600, 'hour')}
        v = int(spec[:-1])
        s = symbols[spec[-1]]
        
        name = "%d %s%s" % (v, s[1], "s" if v>1 else "")
        time = v*s[0]
        
        return name, time

def load(module_name, **kwargs):
    p = path.join(path.dirname(path.realpath(__file__)), module_name + '.py')
    module = imp.load_source(module_name, p)
    classes = inspect.getmembers(module, inspect.isclass)
    for name, cls in classes:
        if issubclass(cls, Plugin) and cls != Plugin:
            return cls
