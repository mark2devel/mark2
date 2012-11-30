from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.application.internet import UNIXServer

import json

import events

class Scrollback:
    length = 200
    index  = 0
    data   = [None] * length
    
    def put(self, line):
        self.data[self.index] = line
        self.index = (self.index + 1) % self.length
    
    def get(self, n):
        i = self.index
        c = 0
        while c < min(n, self.length):
            d = self.data[self.index]
            if d == None: return
            yield d
            i = (i + 1) % self.length
            c =  c + 1
        
    

class AServerProtocol(LineReceiver):
    delimiter = '\n'
    
    tab_last = None
    tab_index = 0
    
    def connectionMade(self):
        self.manager.events.register(self.handle_console, Console)
        self.manager.events.register(self.handle_attach, UserAttach)
        self.manager.events.register(self.handle_detach, UserDetach)
    
    def connectionLost(self, reason):
        self.manager.handle_detach(self.user)
    
    def lineReceived(self, line):
        msg = json.loads(str(line))
        ty = msg["type"]
        
        if ty == "attach":
            self.manager.events.dispatch(UserAttach(user=msg['user']))
        
        if ty == "detach":
            self.manager.events.dispatch(UserDetach(user=msg['user']))
            self.loseConnection()
        
        if ty == "input":
            self.manager.events.dispatch(UserInput(user=msg['user'], line=msg['line']))
        
        if ty == "get_lines":
            for l in self.factory.scrollback.get(msg['line_count']):
                self.send_helper("console", line=l)
                
        if ty == "tab":
            beginning = msg["line"].split(" ")
            end = beginning.pop().lower()
            
            candidates = filter(lambda p: p.lower().startswith(end), self.factory.players)
            if len(candidates) == 0:
                send = msg["data"]
            else:
                i = msg['index'] % len(candidates)
                beginning.append(candidates[i])
                send = " ".join(beginning)
            
            return self.send_helper("tab", line=send)
        
    def send_helper(self, ty, **k):
        k["type"] = ty
        self.sendLine(json.dumps(k))
    
    def handle_console(self, event):
        self.send_helper("console", line=event.line) #TODO: expand this to carry more data
    
    def handle_attach(self, event):
        self.send_helper("attach", user=event.user)
    
    def handle_detach(self, event):
        self.send_helper("detach", user=event.user)



class UserServerFactory(Factory):
    players  = []
    
    def __init__(self, parent):
        self.parent = parent
        self.parent.events.register(self.handle_players, events.StatPlayers)
        self.parent.events.register(self.handle_console, events.Console)
        
        self.scrollback = Scrollback()
    
    def buildProtocol(self, addr):
        p = UserServerProtocol()
        p.manager = self.parent
        p.factory = self
        return p
    
    def handle_players(self, event):
        self.players = event.players
    
    def handle_console(self, event):
        self.scrollback.put(event.line)
    

class UserServer(UNIXServer):
    def __init__(self, parent, socket):
        self.parent = parent
        factory = UserServerFactory(parent)
        UNIXServer.__init__(self, socket, factory)

