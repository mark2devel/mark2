from events import Event

#Raised in manager

class PlayerJoin(Event):
    requires = ('username', 'ip')

class PlayerQuit(Event):
    requires = ('username', 'reason')

class PlayerChat(Event):
    requires = ('username', 'message')
