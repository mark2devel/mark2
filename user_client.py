from twisted.internet.protocol import ClientFactory, Protocol
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor, stdio, task

import blessings

import json
import glob
import os
import os.path
import getpass
import subprocess
import sys

import term_prompt

FORMAT = {
    'attached_server':  'bold green on black',
    'detached_server':  'green on black',
    'current_user':     'bold blue on black',
    'attached_user':    'blue on black',
    'detached_user':    'white on black',
    'console':          'normal',
    'prompt':           'normal',
    'joinpart':         'green',
    'error':            'red'
}


class UserManager:
    client = None
    tab_cache = None
    tab_count = 0
    index = 0
    users = []
    sockets = []
    logged_in = set()
    last_size = (0, 0)
    
    def __init__(self, server, socketdir):
        self.user = getpass.getuser()
        
        self.socketdir = socketdir
        
        self.load_servers()
        
        os.environ['PROCPS_USERLEN'] = '32'
        
        if not self.sockets:
            print 'No servers available.'
            sys.exit(1)
        
        self.term = blessings.Terminal()
        
        self.format = dict(FORMAT)
        
        if not self.term.is_a_tty:
            print 'I need a tty.'
            sys.exit(1)
        
        self.prompt = term_prompt.Prompt(self.refresh_prompt, self.command, self.tab, self.next)
        
        print self.term.enter_fullscreen,
        
        if server:
            self.index = ([s[0] for s in self.sockets]).index(server) or 0
        else:
            self.index = 0
        
        self.focus(self.index)
        
        t = task.LoopingCall(self.refresh_data)
        t.start(10)
        
        stdin = Protocol()
        stdin.dataReceived = self.s_in
        stdio.StandardIO(stdin)
    
    def cap(self, name):
        return getattr(self.term, self.format.get(name, 'normal').replace(' ', '_'))
    
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
    
    def all_users(self):
        w = [line.split(' ', 1)[0] for line in subprocess.check_output(['w', '-sh']).splitlines()]
        return set(w)
    
    def refresh_data(self):
        server_refresh = self.load_servers()
        o = self.logged_in
        self.logged_in = self.all_users()
        if server_refresh or self.logged_in != o:
            self.refresh_prompt()
    
    def draw_serverlist(self):
        servers = [x[0] for x in self.sockets]
        current = self.sockets[self.index][0]
        
        detached = list(sorted(self.logged_in - set(self.users)))
        
        spaces = len(max(servers + self.users + detached, key=len))
        
        size = (spaces + 2, len(servers) + len(self.users) + len(detached))
        
        erase_spaces = ' ' * max(0, self.last_size[0] - size[0])
        
        erase = '{}{}  \n'.format(' ' * (spaces + 2), erase_spaces) * max(0, self.last_size[1] - size[1])
        
        with self.term.location(0, 0):
            for s in servers:
                fmt = self.cap('attached_server' if s == current else 'detached_server')
                print '{0} {1} '.format(fmt, s) + ' ' * (spaces - len(s)) + self.term.normal + erase_spaces
            for u in self.users:
                fmt = self.cap('current_user' if u == self.user else 'attached_user')
                print '{0} {1} '.format(fmt, u) + ' ' * (spaces - len(u)) + self.term.normal + erase_spaces
            for u in detached:
                fmt = self.cap('detached_user')
                print '{0} {1} '.format(fmt, u) + ' ' * (spaces - len(u)) + self.term.normal + erase_spaces
            if erase:
                sys.stdout.write(erase)
        
        self.last_size = size
    
    def server_output(self, line, format=None):
        if format:
            line = self.cap(format) + line
        self.printer(line)
    
    def tab_response(self, line):
        self.prompt.set_prompt(line)
        self.printer()
    
    def printer(self, data=None):
        # beginning of line
        sys.stdout.write('\r')
        
        # if there is any data, write it then get a new line
        sys.stdout.write(self.cap('console') + data + '\n' + self.term.normal if data else '')
        
        # self-explanatory
        self.draw_serverlist()
        
        # make sure we're at the bottom of the terminal
        sys.stdout.write(self.term.move(self.term.height - 1, 0))
        
        # draw our prompt
        sys.stdout.write(self.cap('prompt') + self.term.clear_eol + str(self.prompt) + self.term.normal)
        
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
        
        if current and current not in self.sockets:
            self.sockets.append(current)

        self.sockets = sorted(self.sockets, key=lambda e: e[0])
        
        if current:
            self.index = self.sockets.index(current)
        
        if self.client:
            assert self.sockets[self.index][1] == self.client.socket
        
        if old and self.sockets != old:
            return True
        
    def focus(self, n=0):
        print self.term.clear
        
        if self.client and self.client.alive:
            self.client.alive = False
            try:
                self.client.proto.transport.loseConnection()
            except:
                pass
        
        self.index = n
        self.client = UserClient(self, *self.sockets[self.index])
    
    def next(self, step=1):
        self.focus((self.index + step) % len(self.sockets))
    
    def factory_stopped(self, f):
        self.prompt.clean_up()
        print self.term.exit_fullscreen,


class UserClientProtocol(LineReceiver):
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
            self.manager.server_output(msg["data"], format=msg.get("kind", None))
        
        if ty == "tab":
            self.manager.tab_response(msg["candidate"])
        
        if ty == "userlist":
            self.manager.users = list(sorted(msg["users"]))
            self.manager.refresh_prompt()
        
        if ty == "options":
            self.manager.format.update(msg["format"])
            self.manager.prompt.prefix = msg["prompt"] + ' '
    
    def send_helper(self, ty, **k):
        k["type"] = ty
        #print json.dumps(k)
        self.sendLine(json.dumps(k))
    
    def send_output(self, line):
        self.send_helper("line", data=line)
    

class UserClientFactory(ClientFactory):
    protocol = UserClientProtocol
    
    alive = True
    
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name
    
    def buildProtocol(self, addr):
        p = UserClientProtocol()
        p.name    = self.name
        p.manager = self.parent
        p.factory = self
        self.proto = p
        return p
    
    def stopFactory(self):
        self.parent.factory_stopped(self)
    

def UserClient(parent, name, socket):
    factory = UserClientFactory(parent, name)
    factory.socket = socket
    reactor.connectUNIX(socket, factory)
    return factory


"""def main(socketdir, use_server=None):
    m = UserManager(use_server, socketdir)
    reactor.run()
    return m"""

if __name__ == '__main__':
    print 'Use `mark2 attach` to start this program.'
    sys.exit(0)

