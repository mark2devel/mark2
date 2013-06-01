import json

from twisted.internet import protocol
from twisted.internet import reactor

from mk2.plugins import Plugin
from mk2 import events


class RedisProtocol(protocol.Protocol):
    def __init__(self, parent):
        self.parent = parent

    def request(self, *args):
        self.transport.write(self.encode_request(args))

    def encode_request(self, args):
        lines = []
        lines.append('*' + str(len(args)))
        for a in args:
            if isinstance(a, unicode):
                a = a.encode('utf8')
            lines.append('$' + str(len(a)))
            lines.append(a)
        lines.append('')
        return '\r\n'.join(lines)


class RedisFactory(protocol.ReconnectingClientFactory):
    def __init__(self, parent, channel):
        self.parent = parent
        self.channel = channel

    def buildProtocol(self, addr):
        self.protocol = RedisProtocol(self.parent)
        return self.protocol

    def relay(self, data, channel=None):
        channel = channel or self.channel
        self.protocol.request("PUBLISH", channel, json.dumps(data))


class Redis(Plugin):
    host         = Plugin.Property(default="localhost")
    port         = Plugin.Property(default=6379)
    channel      = Plugin.Property(default="mark2-{server}")
    relay_events = Plugin.Property(default="StatPlayers,PlayerJoin,PlayerQuit,PlayerChat,PlayerDeath")

    def setup(self):
        channel = self.channel.format(server=self.parent.server_name)
        self.factory = RedisFactory(self, channel)
        reactor.connectTCP(self.host, self.port, self.factory)
        for ev in self.relay_events.split(','):
            ty = events.get_by_name(ev.strip())
            if ty:
                self.register(self.on_event, ty)
            else:
                self.console("redis: couldn't bind to event: {0}".format(ev))

    def on_event(self, event):
        self.factory.relay(event.serialize())
