# -*- coding: utf-8 -*-
from os import path
import imp
import inspect
import pkg_resources
import traceback
import sys

from twisted.internet import reactor

from ..events import Hook, ServerInput, ServerStarted, ServerStopping


class PluginLoadError(Exception):
    def __init__(self, message, exc=None):
        self.message = message
        self.exc = exc

    def format(self, name):
        l = ["{0}: {1}".format(name, self.message)]
        if self.exc:
            l += ''.join(traceback.format_exception(*self.exc)).split('\n')
        return l


class PluginLoader(object):
    def __init__(self, search_path):
        self.search_path = search_path


class ResourcePluginLoader(PluginLoader):
    def load_plugin(self, name):
        p = path.join(self.search_path, name + '.py')
        if not pkg_resources.resource_exists('mk2', p):
            return False

        try:
            module = imp.load_source(name, pkg_resources.resource_filename('mk2', p))
            classes = inspect.getmembers(module, inspect.isclass)
            for n, cls in classes:
                if issubclass(cls, Plugin) and not cls is Plugin:
                    return cls
            #if we've reached this point, there's no subclass of Plugin in the file!
            raise PluginLoadError("a file for '{0}' exists, but there is no plugin in it".format(name))
        except Exception:
            raise PluginLoadError("'{0}'' failed to load".format(name), sys.exc_info())

    def find_plugins(self):
        for f in pkg_resources.resource_listdir('mk2', self.search_path):
            if pkg_resources.resource_isdir('mk2', path.join(self.search_path, f)):
                continue
            if f.endswith('.py') and f != '__init__.py':
                yield f[:-3]


class EntryPointPluginLoader(PluginLoader):
    def load_plugin(self, name):
        pl = list(pkg_resources.iter_entry_points('mark2.{0}'.format(self.search_path), name))
        if len(pl) == 0:
            return False
        elif len(pl) > 1:
            def_list = ', '.join(ep.dist.project_name for ep in pl)
            raise PluginLoadError("{0} is multiply provided (by {1})".format(name, def_list))
        # we've established that pl contains exactly one EntryPoint
        ep = pl[0]
        try:
            ep.require()
        except ImportError:
            raise PluginLoadError("couldn't load requirements for {0}".format(name), sys.exc_info())
        try:
            # force reloading
            if ep.module_name in sys.modules:
                del sys.modules[ep.module_name]
            cls = ep.load(require=False)
        except ImportError:
            raise PluginLoadError("couldn't load '{0}'".format(name), sys.exc_info())
        # cls must be a Plugin subclass
        if not issubclass(cls, Plugin):
            raise PluginLoadError("'{0}' was advertised, but is not a Plugin".format(name))
        return cls

    def find_plugins(self):
        for ep in pkg_resources.iter_entry_points('mark2.{0}'.format(self.search_path)):
            yield ep.name


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
            
        return ident

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
    def __init__(self, parent, search_path='plugins', name='plugin',
                 get_config=lambda *a: {}, require_config=False,
                 loaders=(ResourcePluginLoader, EntryPointPluginLoader)):
        self.parent = parent
        self.states = {}
        self.name = name
        self.search_path = search_path
        self.get_config = get_config
        self.require_config = require_config
        self.loaders = []
        for l in loaders:
            self.loaders.append(l(search_path))
        dict.__init__(self)

    def find(self):
        names = set()
        for loader in self.loaders:
            names |= set(loader.find_plugins())
        return list(names)

    def load(self, name):
        kwargs = self.get_config(name)
        if self.require_config and kwargs in (None, False):
            self.parent.console("not loading {0}: no config".format(name))
            return None

        for loader in self.loaders:
            try:
                cls = loader.load_plugin(name)

                # if we can't load the plugin from there just try another
                # loader
                if cls is False:
                    continue

                #instantiate plugin
                plugin = cls(self.parent, name, **kwargs)

                #restore state
                if name in self.states:
                    plugin.load_state(self.states[name])
                    del self.states[name]

                #register plugin
                self[name] = plugin

                return plugin

            except PluginLoadError as e:
                for line in e.format(self.name):
                    self.parent.console(line)
                return None

        self.parent.console("couldn't find plugin: {0}".format(name))

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
        return self.load(name)

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
