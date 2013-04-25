from events import Event


class PlayerEvent(Event):
    def setup(s):
        s.username = s.username.encode('ascii')


#Raised in manager

class PlayerJoin(PlayerEvent):
    requires = ('username', 'ip')


class PlayerQuit(PlayerEvent):
    requires = ('username', 'reason')


class PlayerChat(PlayerEvent):
    requires = ('username', 'message')


class PlayerDeath(PlayerEvent):
    contains = ('text', 'username', 'cause', 'killer', 'weapon')
    requires = ('text', 'username', 'cause')
    killer = None
    weapon = None
