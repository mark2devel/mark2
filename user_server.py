from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.application.internet import UNIXServer

import os
import json

import events

class Scrollback:
    def __init__(self, length):
        self.length = length
        self.data = []

    def put(self, line):
        self.data.append(line)
        if len(self.data) > self.length:
            self.data.pop(0)

    def get(self, max_items = None):
        if max_items is None:
            return self.data[:]
        else:
            return self.data[-max_items:]

class UserServerProtocol(LineReceiver):
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
        
        elif ty == "get_lines":
            for e in self.factory.scrollback.get(msg['line_count']):
                self.console_helper(e)
        
        elif ty == "get_users":
            for u in self.factory.users:
                self.send_helper("user_status", user=u, online=True)
        
        elif ty == "get_stats":
            self.send_helper("stats", stats=self.factory.stats)
        
        elif ty == "tab":
            beginning = msg["line"].split(" ")
            end = beginning.pop().lower()
            
            candidates = filter(lambda p: p.lower().startswith(end), self.factory.players)
            if len(candidates) == 0:
                send = msg["data"]
            else:
                i = msg['index'] % len(candidates)
                beginning.append(candidates[i])
                send = " ".join(beginning)
            
            self.send_helper("tab", line=send)
        
        else:
            self.factory.parent.console("unknown packet: %s" % str(msg))
        
    def send_helper(self, ty, **k):
        k["type"] = ty
        self.sendLine(json.dumps(k))
    
    def console_helper(self, event):
        self.send_helper("console", **{k: getattr(event, k) for k in event.contains})
    
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
        self.parent.events.register(self.handle_memory,       events.StatMemory)
        self.parent.events.register(self.handle_tick_time,    events.StatTickTime)
        
        self.stats = {k: '___' for k in ('tick_time', 'memory_current', 'memory_max', 'players_current', 'players_max')}
    
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
        self.players = event.players
    
    def handle_memory(self, event):
        self.stats['memory_current'] = event.memory_current
        self.stats['memory_max']     = event.memory_max
    
    def handle_tick_time(self, event):
        self.stats['tick_time'] = event.tick_time


class UserServer(UNIXServer):
    def __init__(self, parent, socket):
        self.parent = parent
        if os.path.exists(socket):
            os.remove(socket)
        factory = UserServerFactory(parent)
        UNIXServer.__init__(self, socket, factory)
