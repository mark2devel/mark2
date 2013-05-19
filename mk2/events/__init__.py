import inspect
import itertools
import sys
import time

from twisted.internet import reactor, task
from twisted.internet.defer import succeed, maybeDeferred


class _EventArg(object):
    def __init__(self, default=None, required=False):
        self.default = default
        self.required = required

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance._args.get(self, self.default)

    def __set__(self, instance, value):
        instance._args[self] = value


class EventMetaclass(type):
    def __init__(cls, name, bases, dict_):
        cls._contains = [n for n, v in inspect.getmembers(cls)
                         if isinstance(v, _EventArg)]
        cls._requires = [n for n in cls._contains if getattr(cls, n).required]
        return type.__init__(cls, name, bases, dict)


class Event(object):
    __metaclass__ = EventMetaclass

    Arg = _EventArg

    EAT = 1
    UNREGISTER = 2

    doc = ''

    def __init__(self, d={}, **args):
        args.update(d)
        self._args = {}

        missing = set(self._requires) - set(args.iterkeys())
        excess = set(args.iterkeys()) - set(self._contains)
        if missing:
            raise Exception("Event type {0} missing argument(s): {1}".
                            format(self.__class__.__name__, ", ".join(missing)))
        elif excess:
            raise Exception("Event type {0} got extraneous argument(s): {1}".
                            format(self.__class__.__name__, ", ".join(excess)))
        for k, v in args.iteritems():
            setattr(self, k, v)

        self.setup()

    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError:
            raise IndexError

    @classmethod
    def _prefilter_argcheck(cls, args):
        spec = inspect.getargspec(cls.prefilter)

        args = set(args.iterkeys())
        required_args = set(spec.args[1:-len(spec.defaults or [])])

        if required_args - args:
            return (False, "missing arguments for prefilter: {0}".format(
                    ", ".join(required_args - args)))
        if spec.keywords is None:
            allowed_args = set(spec.args[1:])
            if args - allowed_args:
                return (False, "excess arguments for prefilter: {0}".format(
                    ", ".join(args - allowed_args)))
        return (True, "")

    def prefilter(self):
        return True

    def setup(self):
        pass

    def serialize(self):
        data = dict((k, getattr(self, k)) for k in self._contains)
        data['class_name'] = self.__class__.__name__
        return data

    def __repr__(self):
        return "{0}({1})".format(self.__class__.__name__, self.serialize())


class EventPriority:
    def __init__(self, priority=None, monitor=False):
        self.priority, self.monitor = priority, monitor

    def __str__(self):
        return "P{0}".format(self.priority)

    def __repr__(self):
        return str(self)

    def __call__(self, f):
        f._mark2_priority = self
        return f

EventPriority.MONITOR = EventPriority( 0)
EventPriority._LOW    = EventPriority(10)
EventPriority.LOWEST  = EventPriority(20)
EventPriority.LOW     = EventPriority(30)
EventPriority.MEDIUM  = EventPriority(40)
EventPriority.HIGH    = EventPriority(50)
EventPriority.HIGHEST = EventPriority(60)
EventPriority._HIGH   = EventPriority(70)


class EventList:
    def __init__(self):
        self._cache = None
        self._i = 0
        self._istack = []
        self._handlers = {}

    def _invalidate(self):
        self._cache = None

    def _build_cache(self):
        def key(i):
            return i[1][0].priority
        handlers = itertools.groupby(sorted(self._handlers.iteritems(),
                                            key=key,
                                            reverse=True), key)
        handlers = (l for group, l in handlers)
        handlers = ((i,) + h for l in handlers for i, (p, h) in l)
        self._cache = list(handlers)

    def _get_cache(self):
        if self._cache is None:
            self._build_cache()
        return self._cache

    def _newid(self):
        if self._istack:
            return self._istack.pop()
        else:
            self._i += 1
            return self._i

    def __iter__(self):
        return (h for h in self.cache)

    @property
    def cache(self):
        return list(self._get_cache())

    def add_handler(self, priority, *a):
        self._invalidate()
        i = self._newid()
        self._handlers[i] = (priority, a)
        return i

    def remove_handler(self, id_):
        assert id_ in self._handlers, "{0} is not registered".format(id_)
        self._invalidate()
        del self._handlers[id_]
        self._istack.append(id_)


class EventDispatcher:
    def __init__(self, error_handler):
        self.registered = {}
        self.error_handler = error_handler

    def get(self, event_type):
        return self.registered.get(event_type, [])

    def register(self, callback, event_type, priority=None, **prefilter_args):
        if not event_type in self.registered:
            self.registered[event_type] = EventList()
        d = self.registered[event_type]

        if priority is None:
            if hasattr(callback, '_mark2_priority'):
                priority = callback._mark2_priority
            else:
                priority = EventPriority.MEDIUM

        ok, errmsg = event_type._prefilter_argcheck(prefilter_args)
        if not ok:
            raise Exception("prefilter argument error: " + errmsg)

        return (event_type, d.add_handler(priority, callback, prefilter_args))

    def registerConsumer(self, event_type, callback=None, **kw):
        def _callback(e):
            if callback:
                callback()
            return Event.EAT | Event.UNREGISTER

        return self.register(_callback, event_type, **kw)

    def unregister(self, id_):
        event_type, id_ = id_
        self.registered[event_type].remove_handler(id_)

    def _next_event(self, event, iter_, handled=False):
        while True:
            try:
                id_, callback, args = iter_.next()
            except StopIteration:
                return succeed(handled)
            if event.prefilter(**args):
                break
        r = maybeDeferred(callback, event)
        # add them in this order so _done_event will still be called
        # if there's an error
        r.addErrback(self._event_errback, event, callback)
        r.addCallback(self._done_event, event, id_, iter_)
        return r

    def _event_errback(self, failure, event, callback):
        self.error_handler(event, callback, failure)

    def _done_event(self, r, event, id_, iter_):
        if type(r) is int:
            if r & Event.UNREGISTER:
                self.registered[event.__class__].remove_handler(id_)
            if r & Event.EAT:
                return True
        return self._next_event(event, iter_, True)

    def dispatch(self, event):
        event_list = iter(self.get(event.__class__))
        d = self._next_event(event, event_list)
        d.addErrback(self._event_errback, event, self.dispatch)
        return d
    
    def dispatch_delayed(self, event, delay):
        t = reactor.callLater(delay, lambda: self.dispatch(event))
        return t
    
    def dispatch_repeating(self, event, interval, now=False):
        t = task.LoopingCall(lambda: self.dispatch(event))
        t.start(interval, now)
        return t


def get_timestamp(t=None):
    if t is None:
        return time.strftime("%Y-%m-%d %H:%M:%S")
    elif len(t) == 8:
        return time.strftime("%Y-%m-%d ") + t
    else:
        return t


#get an event type by name
def get_by_name(name):
    for n, c in get_all():
        if n.lower() == name.lower():
            return c


#get all events
def get_all():
    for n, c in inspect.getmembers(sys.modules[__name__], inspect.isclass):
        if issubclass(c, Event):
            yield n, c


def from_json(data):
    data = json.loads(data)
    return get_by_name(data['name'])(**data['data'])

from console import *
from error   import *
from hook    import *
from player  import *
from server  import *
from stat    import *
from user    import *
