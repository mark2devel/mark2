from events import Event

class Error(Event):
    pass

class FatalError(Event):
    exception = None
    reason    = None
