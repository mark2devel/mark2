from . import Event


class PlayerEvent(Event):
    def setup(s):
        s.username = s.username.encode('ascii')


#Raised in manager

class PlayerJoin(PlayerEvent):
    username = Event.Arg(required=True)
    ip       = Event.Arg(required=True)

class PlayerQuit(PlayerEvent):
    username = Event.Arg(required=True)
    reason   = Event.Arg(required=True)


class PlayerChat(PlayerEvent):
    username = Event.Arg(required=True)
    message  = Event.Arg(required=True)


class PlayerDeath(PlayerEvent):
    text     = Event.Arg()
    username = Event.Arg(required=True)
    cause    = Event.Arg(required=True)
    killer   = Event.Arg()
    weapon   = Event.Arg()
    format   = Event.Arg(default="{username} died")

    def get_text(self, **kw):
        d = dict(((k, getattr(self, k)) for k in ('username', 'killer', 'weapon')))
        d.update(kw)
        return self.format.format(**d)

    def setup(self):
        self.text = self.get_text()
