from events import Event

#All these are raised in user_server

class UserInput(Event):
    requires = ('user', 'line')

class UserAttach(Event):
    requires = ('user',)

class UserDetach(Event):
    requires = ('user',)
