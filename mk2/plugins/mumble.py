import re
import struct

from twisted.application.internet import UDPServer
from twisted.internet import reactor, defer
from twisted.internet.defer import TimeoutError
from twisted.internet.protocol import DatagramProtocol

from mk2.plugins import Plugin
from mk2.events import ServerOutput

class MumbleProtocol(DatagramProtocol):
    buff = ""
    def __init__(self, parent, host, port):
        self.parent = parent
        self.host = host
        self.port = port

    def ping(self, *a):
        self.transport.write('\x00'*12, addr=(self.host, self.port))

    def datagramReceived(self, data, (host, port)):
        self.buff += data
        if len(self.buff) < 24:
            return

        if not self.buff.startswith('\x00\x01\x02\x03' + '\x00' * 8):
            self.parent.console("the mumble server gave us crazy data!")
            self.buff = ""
            return

        d = dict(zip(('users_current', 'users_max', 'bandwidth'), struct.unpack('>III', self.buff[12:24])))

        self.buff = self.buff[24:]

        self.parent.got_response(d)


class Mumble(Plugin):
    host       = Plugin.Property(required=True)
    port       = Plugin.Property(default=64738)
    timeout    = Plugin.Property(default=10)
    trigger    = Plugin.Property(default="!mumble")
    command_up = Plugin.Property(default='''
msg {username} &2host: &a{host}
msg {username} &2port: &a{port}
msg {username} &2status: &aup! users: {users_current}/{users_max}
'''.strip())

    command_down = Plugin.Property(default='''
msg {username} &2host: &a{host}
msg {username} &2port: &a{port}
msg {username} &2status: &adown.
'''.strip())

    def setup(self):
        self.users = []
        self.protocol = MumbleProtocol(self, self.host, self.port)
        self.register(self.handle_trigger, ServerOutput, pattern="<([A-Za-z0-9_]{1,16})> "+re.escape(self.trigger))
        reactor.listenUDP(0, self.protocol)

    def teardown(self):
        self.protocol.transport.loseConnection()

    def handle_trigger(self, event):
        username = event.match.group(1).encode('utf8')
        d = defer.Deferred()
        d.addCallback(lambda d: self.send_response(self.command_up,   username=username, **d))
        d.addErrback (lambda d: self.send_response(self.command_down, username=username))
        #add a timeout
        self.delayed_task(self.got_timeout, self.timeout)
        self.users.append(d)
        self.protocol.ping()

    def got_response(self, d):
        for u in self.users:
            u.callback(d)
        self.users = []
        self.stop_tasks()

    def got_timeout(self, e):
        for u in self.users:
            u.errback(TimeoutError())
        self.users = []
        self.stop_tasks()

    def send_response(self, command, **d):
        self.send_format(command, parseColors=True, host=self.host, port=self.port, **d)
