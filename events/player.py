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
    contains = ('text', 'username', 'cause', 'killer', 'weapon', 'format')
    requires = ('username', 'cause')
    killer = None
    weapon = None
    format = "{username} died"

    def get_text(self, **kw):
        d = dict(((k, getattr(self, k)) for k in ('username', 'killer', 'weapon')))
        d.update(kw)
        return self.format.format(**d)

    @property
    def text(self):
        return self.get_text()
