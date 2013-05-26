# -*- coding: utf-8 -*-
from os import path
import imp
import inspect
import traceback
from pkg_resources import resource_listdir, resource_isdir, resource_exists, resource_filename

from twisted.internet import reactor

from ..events import Hook, ServerInput, ServerStarted, ServerStopping


class Plugin:
    restore = tuple()

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
        track = True
        if 'track' in k:
            track = k['track']
            del k['track']

        ident = self.parent.events.register(*a, **k)

        if track:
            self._events.append(ident)

    def unregister(self, ident):
        self.parent.events.unregister(ident)
        if ident in self._events:
            self._events.remove(ident)

    def unregister_all(self):
        for ident in list(self._events):
            self.unregister(ident)
    
    def save_state(self):
        return [getattr(self, k) for k in self.restore]

    def load_state(self, state):
        [setattr(self, k, state.pop(0)) for k in self.restore]
    
    def delayed_task(self, callback, delay, name=None):
        hook = self._task(callback, name)
        t = self.parent.events.dispatch_delayed(hook, delay)
        t._stop = t.cancel
        t._active = t.active
        self._tasks.append(t)

    def repeating_task(self, callback, interval, name=None, now=False):
        hook = self._task(callback, name)
        t = self.parent.events.dispatch_repeating(hook, interval, now=now)
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

    def send_format(self, l, parseColors=False, **kw):
        kw = dict((k, FormatWrapper(v)) for k, v in kw.iteritems())
        self.send(l.format(**kw), parseColors=parseColors)
    
    def action_chain_cancellable(self, spec, callbackWarn, callbackAction, callbackCancel=None):
        intervals = [self.parse_time(i) for i in spec.split(';')]
        intervals = sorted(intervals, key=lambda a: a[1])

        delayed_call = [None]

        def cancel(*args):
            delayed_call[0].cancel()
            if callbackCancel:
                callbackCancel(*args)
        
        def action_chain_i(i_name, i_delay, i_action):
            delayed_call[0] = reactor.callLater(i_delay, i_action) 
            callbackWarn(i_name)
        
        lastAction = callbackAction
        lastTime   = 0
        totalTime  = 0
        
        for name, time in intervals:
            delay = time-lastTime
            lastAction = lambda name=name,delay=delay,lastAction=lastAction: action_chain_i(name, delay, lastAction)
            lastTime   = time
            totalTime += time
        
        return totalTime, lastAction, cancel

    def action_chain(self, spec, callbackWarn, callbackAction):
        return self.action_chain_cancellable(spec, callbackWarn, callbackAction)[:2]

    def parse_time(self, spec):
        symbols = {'s': (1, 'second'), 'm': (60, 'minute'), 'h': (3600, 'hour')}
        v = int(spec[:-1])
        s = symbols[spec[-1]]
        
        name = "%d %s%s" % (v, s[1], "s" if v>1 else "")
        time = v*s[0]
        
        return name, time


class PluginManager(dict):
    def __init__(self, parent, search_path='plugins'):
        self.parent = parent
        self.states = {}
        self.search_path = search_path
        self.plugins_list = []
        for f in resource_listdir('mk2', search_path):
            if resource_isdir('mk2', path.join(search_path, f)):
                continue
            if f.endswith('.py') and f != '__init__.py':
                self.plugins_list.append(f[:-3])
        dict.__init__(self)

    def find(self):
        return (f for f in self.plugins_list)

    def load(self, name, **kwargs):
        p = path.join(self.search_path, name + '.py')
        if not resource_exists('mk2', p):
            self.parent.console("can't find plugin: '%s'" % name, kind='error')
            return
        try:
            module = imp.load_source(name, resource_filename('mk2', p))
            classes = inspect.getmembers(module, inspect.isclass)
            for n, cls in classes:
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
            self.parent.console("a file for plugin '%s' exists, but there is no plugin in it" % name, kind='error')
        except Exception:
            self.parent.console("plugin '%s' failed to load. stack trace follows" % name, kind='error')
            for l in traceback.format_exc().split("\n"):
                self.parent.console(l, kind='error')

    def unload(self, name):
        plugin = self[name]
        self.states[name] = plugin.save_state()
        plugin.teardown()
        plugin.stop_tasks()
        plugin.unregister_all()
        del self[name]

    def reload(self, name):
        if name in self:
            self.unload(name)
        kwargs = dict(self.parent.config.get_plugins()).get(name, None)
        if not kwargs is None:
            return self.load(name, **kwargs)

    def load_all(self):
        for name, kwargs in self.parent.config.get_plugins():
            self.load(name, **kwargs)

    def unload_all(self):
        for name in self.keys():
            self.unload(name)

    def reload_all(self):
        self.unload_all()
        self.load_all()


class FormatWrapper(str):
    def __getattribute__(self, item):
        a = str.__getattribute__(self, item)
        if not item.startswith('_') and callable(a):
            return a()
        return a
