import inspect, sys, time

ACCEPTED = 1
FINISHED = 2

class Event:
    requires  = [] # required kwargs
    handled   = False
    cancelled = False
    
    def __init__(self, **args):
        left = list(self.requires)
        for n, v in args.iteritems():
            setattr(self, n, v)
            if n in left:
                left.remove(n)
        if len(left) > 0:
            raise Exception("Event type %s missing argument(s): %s" % (self.__class__, ", ".join(left)))
        self.setup()
    
    def setup(self):
        pass
    
    def consider(self, r_args):
        return ACCEPTED

class EventDispatcher:
    registered = {}
    
    #args: [callback] event_type [kwargs ...]
    def register(self, *a, **event_args):
        callback   = a[0] if len(a) == 2 else lambda: True
        event_type = a[-1]
        
        d = self.registered.get(event_type, [])
        d.append((callback, event_args))
        self.registered[event_type] = d
    
    def dispatch(self, event):
        r = False
        for r_callback, r_args in self.get(event.__class__):
            o  = event.consider(r_args)
            r |= o
            if o & ACCEPTED:
                r = True
                r_callback(event)
                if o & FINISHED:
                    self.registered.remove((r_callback, r_args))
                if event.handled:
                    break
        return r & ACCEPTED
    
    def dispatch_delayed(self, event, delay):
        t = reactor.callLater(delay, lambda: self.dispatch(event))
        return t
    
    def dispatch_repeating(self, event, interval):
        t = task.LoopingCall(lambda: self.dispatch(event))
        t.start(interval, now=False)
        return t

    #get a list of handlers in the form (callback, {args...})
    def get(self, event_type):
        return self.registered.get(event_type, [])[::-1]
    
    #get an event type by name
    def event(self, name):
        for n, c in inspect.getmembers(sys.modules[__name__], inspect.isclass):
            if n.lower() == name.lower() and issubclass(c, Event):
                return c

def get_timestamp(t=None):
    if t == None:
        return time.strftime("%Y-%m-%d %H:%M:%S")
    elif len(t) == 8:
        return t.strftime("%Y-%m-%d ") + t
    else:
        return t

from console import *
from error   import *
from hook    import *
from server  import *
from stat    import *
from user    import *
