from events import Event

def setup(s):
    s.username = s.username.encode('ascii')

#Raised in manager

class PlayerJoin(Event):
    requires = ('username', 'ip')
    setup = setup

class PlayerQuit(Event):
    requires = ('username', 'reason')
    setup = setup

class PlayerChat(Event):
    requires = ('username', 'message')
    setup = setup

class PlayerDeath(Event):
    contains = ('text', 'username', 'cause', 'killer', 'weapon')
    requires = ('text', 'username', 'cause')
    setup = setup
    killer = None
    weapon = None