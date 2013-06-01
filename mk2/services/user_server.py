from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver

import os
import json

from mk2 import events
from mk2.plugins import Plugin


class Scrollback:
    def __init__(self, length):
        self.length = length
        self.data = []

    def put(self, line):
        self.data.append(line)
        if len(self.data) > self.length:
            self.data.pop(0)

    def get(self, max_items=None):
        if max_items is None:
            return self.data[:]
        else:
            return self.data[-max_items:]


class UserServerProtocol(LineReceiver):
    MAX_LENGTH = 999999
    delimiter = '\n'
    
    tab_last = None
    tab_index = 0
    
    attached_user = None
    
    def connectionMade(self):
        self._handlers = []
        for callback, ty in (
            (self.console_helper, events.Console),
            (self.handle_attach,  events.UserAttach),
            (self.handle_detach,  events.UserDetach)):
            self._handlers.append(self.register(callback, ty))
    
    def connectionLost(self, reason):
        if self.attached_user:
            self.dispatch(events.UserDetach(user=self.attached_user))

        for i in self._handlers:
            self.unregister(i)
        self._handlers = []
    
    def lineReceived(self, line):
        msg = json.loads(str(line))
        ty = msg["type"]
        
        if ty == "attach":
            self.attached_user = msg['user']
            self.dispatch(events.UserAttach(user=msg['user']))

        elif ty == "input":
            self.dispatch(events.UserInput(user=msg['user'], line=msg['line']))
        
        elif ty == "get_scrollback":
            self.send_helper("regex", patterns=dict(self.factory.parent.config.get_by_prefix('mark2.regex.')))
            self.send_helper("scrollback", lines=[e.serialize() for e in self.factory.scrollback.get()])

        elif ty == "get_users":
            for u in self.factory.users:
                self.send_helper("user_status", user=u, online=True)

        elif ty == "get_stats":
            self.send_helper("stats", stats=self.factory.stats)

        elif ty == "get_players":
            self.send_helper("players", players=self.factory.players)
        
        else:
            self.factory.parent.console("unknown packet: %s" % str(msg))
        
    def send_helper(self, ty, **k):
        k["type"] = ty
        self.sendLine(json.dumps(k))
    
    def console_helper(self, event):
        self.send_helper("console", **event.serialize())
    
    def handle_attach(self, event):
        self.send_helper("user_status", user=event.user, online=True)
    
    def handle_detach(self, event):
        self.send_helper("user_status", user=event.user, online=False)


class UserServerFactory(Factory):
    players = []
    
    def __init__(self, parent):
        self.parent     = parent
        self.scrollback = Scrollback(200)
        self.users      = set()
        
        self.parent.events.register(self.handle_console, events.Console)
        self.parent.events.register(self.handle_attach,  events.UserAttach)
        self.parent.events.register(self.handle_detach,  events.UserDetach)
        
        self.parent.events.register(self.handle_player_count, events.StatPlayerCount)
        self.parent.events.register(self.handle_players,      events.StatPlayers)
        self.parent.events.register(self.handle_process,      events.StatProcess)
        
        self.stats = dict((k, '___') for k in ('memory', 'cpu', 'players_current', 'players_max'))
    
    def buildProtocol(self, addr):
        p = UserServerProtocol()
        p.register   = self.parent.events.register
        p.unregister = self.parent.events.unregister
        p.dispatch   = self.parent.events.dispatch
        p.factory    = self
        return p

    def handle_console(self, event):
        self.scrollback.put(event)
    
    def handle_attach(self, event):
        self.users.add(event.user)
    
    def handle_detach(self, event):
        self.users.discard(event.user)
    
    #stat handlers
    def handle_player_count(self, event):
        self.stats['players_current'] = event.players_current
        self.stats['players_max']     = event.players_max
        
    def handle_players(self, event):
        self.players = sorted(event.players, key=str.lower)
    
    def handle_process(self, event):
        for n in ('cpu', 'memory'):
            self.stats[n] = '{0:.2f}'.format(event[n])


class UserServer(Plugin):
    def setup(self):
        socket = self.parent.socket
        if os.path.exists(socket):
            os.remove(socket)
        self.factory = UserServerFactory(self.parent)
        reactor.listenUNIX(socket, self.factory, mode=self.parent.config.get_umask('sock'))

    def save_state(self):
        return self.factory.players

    def load_state(self, state):
        self.factory.players = state
