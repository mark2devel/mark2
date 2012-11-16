from twisted.internet.protocol import ClientFactory, Protocol
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor, stdio

import blessings

import json
import glob
import os.path
import getpass
import sys

import term_prompt

class AManager:
    client = None
    tab_cache = None
    tab_count = 0
    
    
    def __init__(self):
        self.user = getpass.getuser()
        self.load_servers()
        self.focus()
        self.term = blessings.Terminal()
        print self.term.enter_fullscreen,
        self.prompt = term_prompt.Prompt(self.refresh_prompt, self.command, self.tab)

        stdin = Protocol()
        stdin.dataReceived = self.s_in
        stdio.StandardIO(stdin)

    def s_in(self, d):
        self.prompt.write(d)
        self.printer()
    
    def command(self, d):
        self.client.proto.send_helper("input", data=d)
    
    def tab(self, d, i):
        if d == "":
            self.prompt.write("say ")
        else:
            self.client.proto.send_helper("tab", data=d, index=i)
    
    def refresh_prompt(self):
        #print "prompt refresh"
        self.printer()
    
    def server_output(self, line):
        self.printer(line)
    
    def tab_response(self, line):
        self.prompt.set_prompt(line)
        self.printer()
    
    def printer(self, data=None):
        data = data+"\n" if data else ""
        #print "PRINTING!"
        sys.stdout.write("\r%s%s%s" % (self.term.clear_eol, data, str(self.prompt)))
        sys.stdout.flush()
        #if data:
        #    print data
        #print self.prompt,
            
    
    def load_servers(self):
        self.sockets = []
        for f in glob.glob('/tmp/mcpitch/*.sock'):
            name = os.path.splitext(os.path.basename(f))[0]
            self.sockets.append((name, f))

        self.sockets = sorted(self.sockets, key=lambda e: e[0])
        
    def focus(self, n=0):
        if self.client:
            self.client.shutdown()
        
        self.client = AClient(self, *self.sockets[n])

    def factory_stopped(self):
        self.prompt.clean_up()
        print self.term.exit_fullscreen,

class AClientProtocol(LineReceiver):
    user = None
    delimiter = '\n'
    
    def connectionMade(self):
        #print "client connected!"
        self.send_helper("attach", user=self.manager.user, line_count=self.manager.term.height)

    def connectionLost(self, reason):
        print "client disconnected!"

    def lineReceived(self, line):
        msg = json.loads(line)
        ty = msg["type"]
        
        if ty == "output": 
            self.manager.server_output(msg["data"])
        
        if ty == "tab":
            self.manager.tab_response(msg["candidate"])
        
        
    
    def send_helper(self, ty, **k):
        k["type"] = ty
        #print json.dumps(k)
        self.sendLine(json.dumps(k))
    
    def send_output(self, line):
        self.send_helper("line", data=line)
    


class AClientFactory(ClientFactory):
    protocol = AClientProtocol
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name
    
    def buildProtocol(self, addr):
        p = AClientProtocol()
        p.name    = self.name
        p.manager = self.parent
        p.factory = self
        self.proto = p
        return p
    
    def stopFactory(self):
        self.parent.factory_stopped()
        
def AClient(parent, name, socket):
    factory = AClientFactory(parent, name)
    reactor.connectUNIX(socket, factory)
    return factory

def main():
    m = AManager()
    reactor.run()

if __name__ == '__main__':
    main()
