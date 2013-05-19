from . import Event

#All these are raised in user_server

class UserInput(Event):
    user = Event.Arg(required=True)
    line = Event.Arg(required=True)

class UserAttach(Event):
    user = Event.Arg(required=True)

class UserDetach(Event):
    user = Event.Arg(required=True)
