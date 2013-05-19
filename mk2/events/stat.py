from . import Event


class StatEvent(Event):
    source = Event.Arg()


#provider: ping
class StatPlayerCount(StatEvent):
    players_current = Event.Arg(required=True)
    players_max     = Event.Arg(required=True)


#provider: console tracking
class StatPlayers(StatEvent):
    players = Event.Arg(required=True)


#provider: psutil
class StatProcess(StatEvent):
    cpu    = Event.Arg(required=True)
    memory = Event.Arg(required=True)
