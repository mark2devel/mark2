from events import Event

#Raised in manager

class PlayerJoin(Event):
    requires = ('username', 'ip')

class PlayerQuit(Event):
    requires = ('username', 'reason')

class PlayerChat(Event):
    requires = ('username', 'message')

class PlayerDeath(Event):
    contains = ('text', 'username', 'cause', 'killer', 'weapon')
    requires = ('text', 'username', 'cause')
    killer = None
    weapon = None