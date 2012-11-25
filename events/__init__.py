class Event:
    requires = []                  # required kwargs
    acc_i = False                  # dispatch() return accumulator initial value
    acc_m = lambda s, a, b: a or b # dispatch() return accumulator reduction method
    dispatch_once = False          # Only dispatch the event to one handler
    handle_once   = False          # Delete a handler after its first use
    
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
        return True
    
    def extra(self, r_args):
        return {}

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
        o = event.acc_i
        for r_callback, r_args in self.registered.get(event.__class__, []):
            if event.consider(r_args):
                for k, v in event.extra(r_args).iteritems():
                    setattr(event, k, v)
                o = event.acc_m(o, bool(r_callback(event)))
                if event.handle_once:
                    self.registered.remove(r_callback, r_args)
                if event.dispatch_once:
                    break
        return o
    
    def dispatch_delayed(self, event, delay):
        t = reactor.callLater(delay, lambda: self.dispatch(event))
    
    def dispatch_repeating(self, event, interval):
        t = task.LoopingCall(lambda: self.dispatch(event))
        t.start(interval, now=False)

from hook import Hook
from line import Line
from line_consumer import LineConsumer
from raw_line import RawLine
from shutdown import Shutdown

