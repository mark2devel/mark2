from . import Event


class Error(Event):
    pass


class FatalError(Event):
    exception = Event.Arg()
    reason    = Event.Arg()
