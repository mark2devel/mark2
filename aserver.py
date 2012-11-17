from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor

import json

class AServerProtocol(LineReceiver):
    user = None
    delimiter = '\n'
    
    tab_last = None
    tab_index = 0
    
    def connectionMade(self):
        #print "client connected!"
        pass
    
    def connectionLost(self, reason):
        self.manager.handle_detach(self.user)
    
    def send_helper(self, ty, **k):
        k["type"] = ty
        self.sendLine(json.dumps(k))
    
    def send_output(self, line):
        self.send_helper("output", data=line)
    
    def lineReceived(self, line):
        msg = json.loads(str(line))
        
        ty = msg["type"]
        
        #Client tells us who they are
        if ty == "attach":
            self.user = msg["user"]
            self.manager.handle_attach(self, msg["user"], msg["line_count"])
        #elif not self.user:
        #    return {"ty": "error", "data": "not identified."}
        #if ty == "detach":
        #    self.manager.handle_detach(self, msg["user"])
        
        #Tab-complete player name
        if ty == "tab":
            beginning = msg["data"].split(" ")
            end = beginning.pop().lower()
            
            candidates = filter(lambda p: p.lower().startswith(end), self.manager.players)
            if len(candidates) == 0:
                send = msg["data"]
            else:
                i = msg['index'] % len(candidates)
                beginning.append(candidates[i])
                send = " ".join(beginning)
            
            return self.send_helper("tab", candidate=send)

        #Command-line input
        if ty == "input":
            d = msg["data"]
            if d.startswith("#"):
                self.manager.handle_chat(self.user, d[1:])
            elif d.startswith("~"):
                self.manager.handle_plugin(self.user, *d[1:].split(".", 1))
            else:
                self.manager.handle_command(self.user, d)
        

class AServerFactory(Factory):
    protocol = AServerProtocol
    def __init__(self, parent):
        self.parent = parent
    
    def buildProtocol(self, addr):
        p = AServerProtocol()
        p.manager = self.parent
        p.factory = self
        
        return p
        

def AServer(parent):
    factory = AServerFactory(parent)
    reactor.listenUNIX(parent.socket, factory)
    return factory
