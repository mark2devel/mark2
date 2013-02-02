# -*- coding: utf-8 -*-
from os import path
import imp
import inspect
import re
import traceback

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
        
        self._tasks = []
        self._events = []
        self._services = []
    
        for n, v in kwargs.iteritems():
            setattr(self, n, v)
        
        self.register(self.server_started, ServerStarted)
        self.register(self.server_stopping, ServerStopping)
        
        self.setup()

    #called on plugin load
    def setup(self):
        pass

    #called on plugin unload
    def teardown(self):
        pass
    
    def server_started(self, event):
        pass
    
    def server_stopping(self, event):
        self.stop_tasks()
    
    def register(self, *a, **k):
        ident = self.parent.events.register(*a, **k)
        track = True
        if 'track' in k:
            track = k['track']
            del k['track']

        if track:
            self._events.append(ident)

    def unregister(self, ident):
        self.parent.events.unregister(ident)
        if ident in self._events:
            self._events.remove(ident)

    def unregister_all(self):
        for ident in self._events:
            self.unregister(ident)
    
    def save_state(self):
        pass

    def load_state(self, state):
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
        self.dispatch(ServerInput(line=l, parse_colors=parseColors))
    
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




class PluginManager(dict):
    def __init__(self, parent):
        self.parent = parent
        self.states  = {}
        dict.__init__(self)

    def load(self, module_name, **kwargs):
        self.parent.console("... loading: %s" % module_name)
        found = False
        p = path.join(path.dirname(path.realpath(__file__)), module_name + '.py')
        try:
            module = imp.load_source(module_name, p)
            classes = inspect.getmembers(module, inspect.isclass)
            for name, cls in classes:
                if issubclass(cls, Plugin) and not cls is Plugin:
                    #instantiate plugin
                    plugin = cls(self.parent, name, **kwargs)

                    #restore state
                    if name in self.states:
                        plugin.load_state(self.states[name])
                        del self.states[name]

                    #register plugin
                    self[name] = plugin

                    #return
                    return plugin

            #if we've reached this point, there's no subclass of Plugin in the file!
            raise Exception("Couldn't find class!")
        except Exception:
            self.parent.console("plugin '%s' failed to load. stack trace follows" % module_name, kind='error')
            for l in traceback.format_exc().split("\n"):
                self.parent.console(l, kind='error')

    def unload(self, name):
        self.parent.console("... unloading: %s" % name)
        plugin = self[name]
        self.states[name] = plugin.save_state()
        plugin.teardown()
        plugin.stop_tasks()
        plugin.unregister_all()
        del self[name]

    def reload(self, name):
        self.unload(name)
        kwargs = self.parent.config.get_plugins().get(name, None)
        if not kwargs is None:
            self.load(name, **kwargs)

    def load_all(self):
        for name, kwargs in self.parent.config.get_plugins():
            self.load(name, **kwargs)

    def unload_all(self):
        for name in self.keys():
            self.unload(name)

    def reload_all(self):
        self.unload_all()
        self.load_all()