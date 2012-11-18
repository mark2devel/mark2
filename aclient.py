from twisted.internet.protocol import ClientFactory, Protocol
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor, stdio, task

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
    index = 0
    users = []
    last_users = []
    sockets = []
    last_sockets = []
    
    
    def __init__(self, server, socketdir):
        self.user = getpass.getuser()
        
        self.socketdir = socketdir
        
        self.load_servers()
        
        if not self.sockets:
            print 'No servers available. Press Ctrl-C to exit.'
            return
        
        self.term = blessings.Terminal()
        self.prompt = term_prompt.Prompt(self.refresh_prompt, self.command, self.tab, self.next)
        
        print self.term.enter_fullscreen,
        
        if server:
            self.index = ([s[0] for s in self.sockets]).index(server) or 0
        else:
            self.index = 0
        
        self.focus(self.index)
        
        t = task.LoopingCall(self.load_servers)
        t.start(10)

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
    
    def draw_serverlist(self):
        servers = [x[0] for x in self.sockets]
        last_servers = [x[0] for x in self.last_sockets]
        current = self.sockets[self.index][0]
        
        spaces = len(max(servers + self.users, key=len))
        erase_spaces = max(0, len(max(self.last_users + last_servers + servers, key=len)) - spaces) * ' '
        
        erase = max(0, len(self.last_users) + len(last_servers) - len(self.users) - len(self.sockets))
        
        with self.term.location(0, 0):
            for s in servers:
                fmt = self.term.bold_green_on_black if s==current else self.term.green_on_black
                print '{fmt} {s} '.format(**locals()) + ' ' * (spaces-len(s)) + self.term.normal + erase_spaces
            for u in self.users:
                fmt2 = self.term.bold_blue_on_black if u==self.user else self.term.blue_on_black
                print '{fmt2} {u} '.format(**locals()) + ' ' * (spaces-len(u)) + self.term.normal + erase_spaces
            if erase:
                sys.stdout.write((' ' * (spaces + 2) + erase_spaces + '\n') * erase)
        
        self.last_users = self.users
        self.last_sockets = self.sockets
    
    def server_output(self, line):
        self.printer(line)
    
    def tab_response(self, line):
        self.prompt.set_prompt(line)
        self.printer()
    
    def printer(self, data=None):
        # beginning of line
        sys.stdout.write('\r')
        
        # if there is any data, write it then get a new line
        sys.stdout.write(data + '\n' if data else '')
        
        # self-explanatory
        self.draw_serverlist()
        
        # make sure we're at the bottom of the terminal
        sys.stdout.write(self.term.move(self.term.height - 1, 0) + self.term.clear_eol)
        
        # draw our prompt
        sys.stdout.write(str(self.prompt))
        
        # self-explanatory
        try:
            sys.stdout.flush()
        except IOError:
            pass
    
    def load_servers(self):
        current = self.sockets[self.index] if self.sockets else None
        old = self.sockets if self.sockets else []
        self.sockets = []
        
        for f in glob.glob(os.path.join(self.socketdir, '*.sock')):
            name = os.path.splitext(os.path.basename(f))[0]
            self.sockets.append((name, f))
        
        if current and current not in self.sockets: self.sockets.append(current)
        self.sockets = sorted(self.sockets, key=lambda e: e[0])
        if current: self.index = self.sockets.index(current)
        if old and self.sockets != old: self.refresh_prompt()
        
        if self.client: assert self.sockets[self.index][1] == self.client.socket
        
    def focus(self, n=0):
        print self.term.clear
        
        if self.client and self.client.alive:
            self.client.alive = False
            try:
                self.client.proto.transport.loseConnection()
            except:
                pass
        
        self.index = n
        self.client = AClient(self, *self.sockets[self.index])
    
    def next(self, step=1):
        self.focus((self.index + step) % len(self.sockets))
    
    def factory_stopped(self, f):
        if not f.alive:
            return
        self.prompt.clean_up()
        print self.term.exit_fullscreen,

class AClientProtocol(LineReceiver):
    user = None
    delimiter = '\n'
    
    def connectionMade(self):
        #print "client connected!"
        self.send_helper("attach", user=self.manager.user, line_count=self.manager.term.height)

    def connectionLost(self, reason):
        if len(self.manager.sockets) <= 1:
            print "client disconnected!"
            #reactor.stop()
        elif self.factory.alive:
            self.manager.next()

    def lineReceived(self, line):
        msg = json.loads(line)
        ty = msg["type"]
        
        if ty == "output": 
            self.manager.server_output(msg["data"])
        
        if ty == "tab":
            self.manager.tab_response(msg["candidate"])
        
        if ty == "userlist":
            self.manager.users = msg["users"]
            self.manager.refresh_prompt()
    
    def send_helper(self, ty, **k):
        k["type"] = ty
        #print json.dumps(k)
        self.sendLine(json.dumps(k))
    
    def send_output(self, line):
        self.send_helper("line", data=line)
    


class AClientFactory(ClientFactory):
    protocol = AClientProtocol
    
    alive = True
    
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
        self.parent.factory_stopped(self)
        
def AClient(parent, name, socket):
    factory = AClientFactory(parent, name)
    factory.socket = socket
    reactor.connectUNIX(socket, factory)
    return factory

def main(socketdir, use_server=None):
    m = AManager(use_server, socketdir)
    reactor.run()

if __name__ == '__main__':
    print 'Use `mark2 attach` to start this program.'
    sys.exit(0)

