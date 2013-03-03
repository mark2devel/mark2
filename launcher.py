import re
import os
import sys
import glob
import stat
import time

#start:
import subprocess

#attach:
import user_client

#stop/kill
#import signal
import errno

#send
import json
import socket

#jar-list/jar-get
from twisted.internet import reactor
import servers


#so, guido says using native python data structures is better than objects wherever possible..
#     options  name        data         description
help_commands = (
    ('',      'help',     '[COMMAND]', 'display help and available options'),
    ('bnwoi', 'start',    '[PATH]',    'start a server'),
    ('b',     'list',     '',          'list running servers'),
    ('bn',    'attach',   '',          'attach to a server'),
    ('bnwoi', 'stop',     '',          'stop mark2'),
    ('bnwoi', 'kill',     '',          'kill mark2'),
    ('bnwoi', 'send',     'INPUT...',  'send a console command'),
    ('',      'jar-list', '',          'list server jars'),
    ('',      'jar-get',  'NAME',      'download a server jar'))

help_options = {
    'b': ('-b  --base', 'PATH',  'the directory to put mark2-related temp files (default: /tmp/mark2)'),
    'n': ('-n  --name', 'NAME',  'choose this named server (useful if you run more than one)'),
    'w': ('-w  --wait', 'REGEX', 'wait for this line of output to appear on console before returning.'),
    'o': ('-o  --only', '',      'print the matched line and no others'),
    'i': ('-i  --immediate', '', 'don\'t wait for any output')

}

usage_text = "usage: mark2 [options] command ..."

help_text = """
mark2 is a minecraft server wrapper

{usage}

commands:
{commands}

examples:
  mark2 start /home/you/mcservers/pvp
  mark2 attach
  mark2 send say hello!
  mark2 stop
"""

def columns(data):
    o = []
    for tokens in data:
        line = ""
        for i, token in enumerate(tokens):
            line += token
            line += " "*(((i+1)*12)-len(line))
        o.append(line)

    return "\n".join(("  "+l for l in o))

help_text = help_text.format(usage=usage_text, commands=columns((c[1:] for c in help_commands)))

class Mark2Error(Exception):
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return "error: %s" % self.error

class Mark2ParseError(Mark2Error):
    def __str__(self):
        return "%s\nparse error: %s" % (usage_text, self.error)


def make_writable(directory):
    need_modes = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH | stat.S_IRWXG | stat.S_IRWXO
    good_modes = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO | stat.S_ISVTX

    if not os.path.exists(directory):
        os.makedirs(directory, good_modes)

    st = os.stat(directory)
    if (st.st_mode & need_modes) == need_modes:
        return True

    try:
        os.chmod(directory, good_modes)
        return True
    except Exception:
        raise Mark2Error('{} does not have the necessary modes to run mark2 and I do not have\npermission to change them!'.format(directory))

def check_config():
    path_old = 'resources/mark2.default.properties'
    path_new = 'config/mark2.properties'

    if not os.path.exists(path_new):
        make_writable('config')
        file_old = open(path_old, 'r')
        file_new = open(path_new, 'w')

        l = ''
        while l.strip() == '' or l.startswith('### ###'):
            l = file_old.readline()

        while l != '':
            file_new.write(l)
            l = file_old.readline()

        file_old.close()
        file_new.close()

        print 'I\'ve created a default configuration file at {}'.format(path_new)
        response = raw_input('Would you like to edit it now? [yes]') or 'yes'
        if response == 'yes':
            try:
                subprocess.call(['sensible-editor', path_new])
            except Exception:
                raise Mark2Error('couldn\'t start editor')

class Skeleton:
    def __init__(self, shared_path, server_name=None, server_path=None, jar_file=None, script_path=None):
        self.shared_path = shared_path
        self.script_path = script_path

        self.servers = self.get_servers()

        if server_name:
            self.server_name = server_name
        else:
            if len(self.servers) > 0:
                self.server_name = self.servers[0]
            else:
                raise Mark2Error("no servers running!")

        self.server_path = server_path
        self.jar_file    = jar_file

    def shared(self, ty, name=None):
        if name is None:
            name = self.server_name

        return os.path.join(self.shared_path, "%s.%s" % (name, ty))

    def get_servers(self):
        o = []
        for path in glob.glob(self.shared('pid', '*')):
            with open(path) as fp:
                pid = int(fp.read())
                try:
                    os.kill(pid, 0)
                except OSError as err:
                    if err.errno == errno.ESRCH:
                        os.remove(path)
                        continue
            f = os.path.basename(path)
            f = os.path.splitext(f)[0]
            o.append(f)

        return sorted(o)

    def is_running(self):
        return self.server_name in self.servers

    def kill(self, sig):
        f = open(self.shared('pid'), 'r')
        pid = int(f.read())
        f.close()
        os.kill(pid, sig)

    def wait(self, *a):
        try:
            self.real_wait(*a)
        except KeyboardInterrupt:
            return

    def real_wait(self, only, exp):
        with open(self.shared('log'), 'r') as f:
            f.seek(0,2)
            while True:
                line = f.readline().rstrip()
                if not line:
                    time.sleep(0.1)
                    continue

                if line[0] in (" ", "\t"):
                    print line
                    continue

                line = line.split(" ", 3)
                if line[2] == '[mark2]':
                    line2 = line[3].split(" ", 2)
                    if re.search(exp, line2[2]):
                        print line[3]
                        return
                    elif not only:
                        print line[3]


    def do_start(self):
        #clear remnants
        for x in ('log', 'sock', 'pid'):
            if os.path.exists(self.shared(x)):
                os.remove(self.shared(x))

        #build command
        command = [
                'twistd',
                '--pidfile', self.shared('pid'),
                '--logfile', self.shared('log'),
                'mark2',
                '--shared-path', self.shared_path,
                '--server-name', os.path.basename(self.server_name),
                '--server-path', self.server_path]

        if self.jar_file:
            command += ['--jar-file', self.jar_file]

        env = dict(os.environ)
        pp = env.get('PYTHONPATH', '')
        if len(pp) > 0:
            env['PYTHONPATH'] = self.script_path + ':' + pp
        else:
            env['PYTHONPATH'] = self.script_path

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        stdout, stderr = [s.strip() for s in process.communicate()]
        if stderr != '':
            print stderr
            raise Mark2Error("twistd failed to start up!")

    def do_list(self):
        for server in self.servers:
            print server

    def do_attach(self):
        f = user_client.UserClientFactory(self.server_name, self.shared_path)
        f.main()

    def do_stop(self):
        #self.kill(signal.SIGINT)
        self.do_send('~stop')

    def do_kill(self):
        #self.kill(signal.SIGKILL)
        self.do_send('~kill')

    def do_send(self, data):
        d = {
            'type': 'input',
            'user': '@external',
            'line': data
        }
        d = json.dumps(d) + "\n"

        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self.shared('sock'))
        s.send(d)
        s.close()

def main():
    immediate   = None
    only        = False
    wait        = None
    shared_path = '/tmp/mark2'
    script_path = sys.path[0]
    server_name = None
    command = None

    #check required binaries
    r_need = ('java',)
    try:
        subprocess.check_output(['which',] + list(r_need), stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError, e:
        r_have = { os.path.basename(s) for s in e.output.split('\n') }
        r_diff = r_need - r_have
        raise Mark2Error("unfulfilled dependencies: %s" % ', '.join(r_diff))

    args = sys.argv[1:]

    while len(args) > 0:
        if args[0].startswith('-'):
            a = args.pop(0)
            if a in ('-i', '--immediate'):
                immediate = True
            elif a in ('-o', '--only'):
                only = True
            elif a in ('-w', '--wait'):
                immediate = False
                wait = args.pop(0)
            elif a in ('-b', '--base'):
                shared_path = args.pop(0)
            elif a in ('-n', '--name'):
                server_name = args.pop(0)
            else:
                raise Mark2ParseError("unknown flag: " + a)
        elif not command:
            command = args.pop(0)
        else:
            break

    if command is None or command == 'help':
        if len(args) == 0:
            print help_text
        else:
            subcommand = args[0]
            details = [c for c in help_commands if c[1] == subcommand]
            if len(details)==0:
                raise Mark2Error("unknown command: %s" % subcommand)
            else:
                details = details[0]

            print """
mark2 {subcommand}: {description}

usage: mark2 {subcommand} {data}
""".format(subcommand=details[1], data=details[2], description=details[3])
            if len(details[0]) > 0:
                print "options:"
                print columns(help_options[c] for c in details[0]) + "\n"

    elif command == 'start':
        #get server path
        if len(args) == 0:
            server_path = ""
        elif len(args) == 1:
            server_path = args[0]
        else:
            raise Mark2ParseError("unknown token after server path: " + " ".join(args[1:]))
        server_path = os.path.abspath(server_path)

        #check path exists and parse a path to a .jar
        jar_file = None
        if os.path.isdir(server_path):
            pass
        elif os.path.isfile(server_path):
            if server_path.endswith('.jar'):
                server_path, jar_file = os.path.split(server_path)
            else:
                raise Mark2Error("unknown file type: " + server_path)
        else:
            raise Mark2Error("path does not exist: " + server_path)

        #get server name
        if server_name is None:
            server_name = os.path.basename(server_path)

        # move to the directory this script is in
        os.chdir(script_path)

        # check we've got config/mark2.properties
        check_config()

        #maked shared path writable
        make_writable(shared_path)

        skel = Skeleton(shared_path, server_name, server_path, jar_file, shared_path)
        if skel.is_running():
            raise Mark2Error("server already running: " + server_name)
        skel.do_start()

        if True if immediate is None else not immediate:
            skel.wait(only, '# mark2 started|stopped\.' if wait is None else wait)

    elif command == 'list':
        if len(args) > 0:
            raise Mark2ParseError("unknown token: " + " ".join(args))
        skel = Skeleton(shared_path)
        skel.do_list()

    elif command == 'attach':
        if len(args) > 0:
            raise Mark2ParseError("unknown token: " + " ".join(args))
        # move to the directory this script is in
        os.chdir(script_path)
        skel = Skeleton(shared_path, server_name)
        if not skel.is_running():
            raise Mark2Error("server not running: " + server_name)
        skel.do_attach()
    elif command == 'stop':
        if len(args) > 0:
            raise Mark2ParseError("unknown token: " + " ".join(args))
        skel = Skeleton(shared_path, server_name)
        if not skel.is_running():
            raise Mark2Error("server not running: " + server_name)
        skel.do_stop()
        if True if immediate is None else not immediate:
            skel.wait(only, '# mark2 stopped\.' if wait is None else wait)
    elif command == 'kill':
        if len(args) > 0:
            raise Mark2ParseError("unknown token: " + " ".join(args))
        skel = Skeleton(shared_path, server_name)
        if not skel.is_running():
            raise Mark2Error("server not running: " + server_name)
        skel.do_kill()
        if True if immediate is None else not immediate:
            skel.wait(only, '# mark2 stopped\.' if wait is None else wait)
    elif command == 'send':
        if len(args) == 0:
            raise Mark2ParseError("nothing to send!")
        skel = Skeleton(shared_path, server_name)
        if not skel.is_running():
            raise Mark2Error("server not running: " + server_name)
        skel.do_send(" ".join(args))
        if wait:
            skel.wait(only, wait)
    elif command == 'jar-list':
        if len(args) > 0:
            raise Mark2ParseError("unknown token: " + " ".join(args))

        def err(what):
            reactor.stop()
            print "error: %s" % what.value

        def handle(listing):
            reactor.stop()
            if len(listing) == 0:
                print "error: no server jars found!"
            else:
                print "The following server jars/zips are available:"
                print listing

        d = servers.jar_list()
        d.addCallbacks(handle, err)
        reactor.run()
    elif command == 'jar-get':
        if len(args) == 0:
            raise Mark2ParseError("missing jar type!")
        elif len(args) == 1:
            name = args[0]
        else:
            raise Mark2ParseError("unknown token after jar type: " + " ".join(args[1:]))

        def err(what):
            reactor.stop()
            print "error: %s" % what.value

        def handle((filename, data)):
            reactor.stop()
            if os.path.exists(filename):
                print "error: %s already exists!" % filename
            else:
                f = open(filename, 'wb')
                f.write(data)
                f.close()
                print "success! saved as %s" % filename

        d = servers.jar_get(name)
        d.addCallbacks(handle, err)
        reactor.run()
    else:
        raise Mark2ParseError("unknown command: " + command)
