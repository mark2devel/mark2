from events import Event

#provider: ping
class StatPlayerCount(Event):
    requires = ('players_current', 'players_max') #int

#provider: console tracking
class StatPlayers(Event):
    requires = ('players',) #list of strings

#provider: psutil
class StatProcess(Event):
    requires = ('cpu', 'memory') #float, float