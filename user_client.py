from twisted.internet.protocol import ClientFactory, Protocol
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor, stdio, task

import blessings

import json
import glob
import os
import getpass
import subprocess
import sys

import term_prompt
from shared import console_repr

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


class AttributeDict(dict):
    def __getattr__(self, attr):
        return self[attr]
        
    def __setattr__(self, attr, value):
        self[attr] = value


class Users:
    def __init__(self):
        self.reset()
        
        os.environ['PROCPS_USERLEN'] = '32'
        self.update_logged_in()

    def attach(self, user):
        self.attached.add(user)
    
    def detach(self, user):
        self.attached.discard(user)
    
    def reset(self):
        self.attached = set()
    
    def update_logged_in(self):
        self.logged_in = set()
        for line in subprocess.check_output(['w', '-sh']).split("\n"):
            self.logged_in.add(line.split(" ", 1)[0])

    def get_all(self):
        for u in self.logged_in:
            yield u, u in self.attached


class UserFactory(ClientFactory):
    client = None  # current client
    stats  = None
    
    def __init__(self, socketdir, server):
        self.socketdir = socketdir
        self.sockets = []
        self.current = (server, os.path.join(socketdir, "%s.sock" % server))
        
        self.user = getpass.getuser()
        self.users = Users()

        self.term = blessings.Terminal()
        self.format = dict(FORMAT)
        if not self.term.is_a_tty:
            self.fatal_error('I need a tty.')
        
        self.prompt = term_prompt.Prompt(
            self.printer,
            self.handle_command,
            self.handle_tab,
            self.switch_server)
        
        print self.term.enter_fullscreen,
        
        if self.current == (None, None):
            self.socket_index = 0
        
        self.switch_server()
        self.printer()
        
        #listen on stdin
        stdin = Protocol()
        stdin.dataReceived = self.prompt.write
        stdio.StandardIO(stdin)
    
        t = task.LoopingCall(self.update_data)
        t.start(3)
        
        reactor.run()
    
    def buildProtocol(self, addr):
        if self.client:
            self.client.clean_up()
        
        p = UserProtocol()
        p.factory = self
        p.addr    = addr
        
        self.client = p
        return p
    
    def stopFactory(self):
        ClientFactory.stopFactory(self)
        self.prompt.clean_up()
        print self.term.exit_fullscreen,
        
        if self.client:
            self.client.clean_up()
        
    def fatal_error(self, err):
        self.stopFactory()
        print err
        if not reactor.running:
            sys.exit(1)
            
    def switch_server(self, move=0):
        print self.term.clear
        
        if self.client:
            self.client.transport.loseConnection()
        
        #Switch to the next socket
        self.update_servers()
        self.socket_index = (self.socket_index + move) % len(self.sockets)
        self.current = self.sockets[self.socket_index]
        
        #Connect!
        reactor.connectUNIX(self.current[1], self)
        return True
      
    def update_servers(self):
        #sockets
        current = self.current
        
        self.sockets = []
        for f in glob.glob(os.path.join(self.socketdir, '*.sock')):
            name = os.path.splitext(os.path.basename(f))[0]
            self.sockets.append((name, f))
        
        self.sockets = sorted(self.sockets, key=lambda x: x[0])
        
        if len(self.sockets) == 0:
            self.fatal_error("no servers running!")
            reactor.stop()
            return
        
        if current != (None, None):
            if current in self.sockets:
                self.socket_index = self.sockets.index(current)
            else:
                self.fatal_error("couldn't find server %s" % current[0])

    def update_data(self):
        self.update_servers()
        self.users.update_logged_in()
        if self.client:
            self.client.update_data()
    
    def cap(self, name):
        return getattr(self.term, self.format.get(name, 'normal').replace(' ', '_'))
    
    def printer(self, data=None):

        ###
        ### Main output
        ###
        # clear the line
        sys.stdout.write('\r' + self.term.clear_eol)
        
        # if there is any data, write it then get a new line
        if data:
            sys.stdout.write(self.cap('console'))
            sys.stdout.write(data + '\n' + self.term.normal)
    
        ###
        ### HEADER!
        ###
        sys.stdout.write(self.term.move(0, 0))
        sys.stdout.write(self.term.clear_eol)
        for name, socket in self.sockets:
            if name == self.current:
                sys.stdout.write(self.term.bold + name + self.term.normal + " ")
            else:
                sys.stdout.write(name + " ")
        
        right = ""
        for user, attached in self.users.get_all():
            if attached:
                right += self.term.bold + user + self.term.normal + " "
            else:
                right += user + " "
        with self.term.location(self.term.width - len(right), 0):
            sys.stdout.write(right)
        
        #second line
        sys.stdout.write("\n" + self.term.clear_eol)
        if self.client and self.stats:
            format = u"tick: {tick_time}ms // mem: {memory_current}MB of {memory_max}MB // players: {players_current} of {players_max}"
            sys.stdout.write(format.format(**self.stats))
        
        # PROMPT
        sys.stdout.write(self.term.move(self.term.height - 1, 0))
        
        # draw our prompt
        sys.stdout.write(self.cap('prompt'))
        sys.stdout.write(str(self.prompt) + self.term.normal)
        try:
            sys.stdout.flush()
        except IOError:
            pass
        
    #prompt handlers:
    def handle_command(self, command):
        if self.client:
            self.client.send_helper("input", line=command, user=self.user)
    
    def handle_tab(self, line, index):
        if line == "":
            self.prompt.write("say ")
        elif self.client:
            self.client.send_helper("tab", line=line, index=index)
    
    #client handlers:
    def handle_output(self, item):
        line = console_repr(item)
        self.printer(line)
    
    def handle_tab_response(self, line):
        self.prompt.set_prompt(line)
        self.printer()
        
    def handle_user_status(self, user, online):
        if online:
            self.users.attach(user)
        else:
            self.users.detach(user)
    
    def handle_stats(self, stats):
        self.stats = stats
        self.printer()
    
    def handle_server_died(self):
        self.socket_index = 0
        self.update_servers()


class UserProtocol(LineReceiver):
    delimiter = '\n'
    
    def connectionMade(self):
        self.alive = 1
        self.send_helper("attach", user=self.factory.user)
        self.send_helper("get_lines", line_count=self.factory.term.height)

    def connectionLost(self, reason):
        self.alive = 0
        self.factory.handle_server_died()

    def lineReceived(self, line):
        msg = json.loads(line)
        ty = msg["type"]
        
        if ty == "console":
            self.factory.handle_output(AttributeDict(msg))
        
        elif ty == "tab":
            self.factory.handle_tab_response(msg["line"])
        
        elif ty == "user_status":
            self.factory.handle_user_status(msg["user"], msg["online"])
        
        elif ty == "stats":
            self.factory.handle_stats(msg["stats"])
        
        else:
            self.factory.printer(line)
    
    def update_data(self):
        self.send_helper("get_users")
        self.send_helper("get_stats")
    
    def send_helper(self, ty, **k):
        k["type"] = ty
        if self.alive:
            self.sendLine(json.dumps(k))
    
    def clean_up(self):
        pass

if __name__ == '__main__':
    print 'Use `mark2 attach` to start this program.'
    sys.exit(0)
