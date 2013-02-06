from events import Event

#provider: ping, query, snoop
class StatPlayerCount(Event):
    requires = ('players_current', 'players_max') #int

#provider: query
class StatPlayers(Event):
    requires = ('players',) #list of strings

#provider: snoop
class StatWorlds(Event):
    requires = ('worlds',) #list of dicts

#provider: query
class StatPlugins(Event):
    requires = ('plugins',) #list of strings

#provider: `top`
class StatThreads(Event):
    requires = ('threads',) #list of dicts