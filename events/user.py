from events import Event

#All these are raised in ATerminal

class UserInput(Event):
    requires = ('username', 'line')

class UserAttached(Event):
    requires = ('username',)

class UserDetached(Event):
    requires = ('username',)
