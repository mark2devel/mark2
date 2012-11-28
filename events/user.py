from events import Event

class UserInput(Event):
    requires = ['line']

class UserAttached(Event):
    requires = ['name']

class UserDetached(Event):
    requires = ['name']
