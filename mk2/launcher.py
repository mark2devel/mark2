import re
import os
import sys
import glob
import stat
import time
import errno

#start:
import subprocess
import getpass
import pwd
import tempfile

#attach:
from . import user_client

#send/stop/kill
import json
import socket

#jar-list/jar-get
from . import servers
from twisted.internet import reactor

usage_text = "usage: mark2 command [options] [...]"

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

help_sub_text = """
mark2 {subcommand}: {doc}

usage: mark2 {subcommand} {value_spec}
"""

class Mark2Error(Exception):
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return "error: %s" % self.error


class Mark2ParseError(Mark2Error):
    def __str__(self):
        return "%s\nparse error: %s" % (usage_text, self.error)


class Command(object):
    name = ""
    value_spec = ""
    options_spec = tuple()
    def __init__(self):
        pass

    def do_start(self):
        self.script_path = sys.path[0]

    def do_end(self):
        pass

    @classmethod
    def get_bases(cls):
        o = []
        while True:
            cls = cls.__bases__[0]
            if cls is object:
                break
            o.append(cls)
        return o

    @classmethod
    def get_options_spec(cls):
        return sum([list(b.options_spec) for b in cls.get_bases()[::-1]], [])

    def parse_options(self, c_args):
        options = {}
        options_tys = {}
        #transform
        for opt in self.__class__.get_options_spec():
            for flag in opt[1]:
                options_tys[flag] = opt


        while len(c_args) > 0:
            head = c_args[0]

            if head[0] != '-':
                break
            elif head == '--':
                c_args.pop(0)
                break
            elif head in options_tys:
                opt = options_tys[c_args.pop(0)]
                try:
                    options[opt[0]] = c_args.pop(0) if opt[2] != '' else True
                except IndexError:
                    raise Mark2ParseError("option `%s` missing argument" % opt[0])
            else:
                raise Mark2Error("%s: unknown option %s" % (self.name, head))


        self.options = options
        self.value = ' '.join(c_args) if len(c_args) else None

    def start(self):
        bases = self.__class__.get_bases()
        for b in bases[::-1]:
            b.do_start(self)
        self.run()
        for b in bases:
            b.do_end(self)

    def run(self):
        raise NotImplementedError


class CommandTyStateful(Command):
    options_spec = (('base', ('-b', '--base'), 'PATH',  'the directory to put mark2-related temp files (default: /tmp/mark2)'),)

    def do_start(self):
        self.shared_path = self.options.get('base', '/tmp/mark2')
        self.make_writable(self.shared_path)

        #get servers
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

        self.servers = sorted(o)

    def shared(self, ty, name=None):
        if name is None:
            name = self.server_name
        return os.path.join(self.shared_path, "%s.%s" % (name, ty))

    def make_writable(self, directory):
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
            raise Mark2Error('%s does not have the necessary modes to run mark2 and I do not have permission to change them!' % directory)


class CommandTySelective(CommandTyStateful):
    options_spec = (('name', ('-n', '--name'), 'NAME',  'create or select a server with this name'),)

    name_should_exist = True
    server_name = None

    def do_start(self):
        name = self.options.get('name', None)
        if self.name_should_exist:
            if name is None:
                if len(self.servers) > 0:
                    name = self.servers[0]
                else:
                    raise Mark2Error("no servers running!")
            elif name not in self.servers:
                raise Mark2Error("server not running: %s" % name)
        else:
            if name is None:
                pass #CommandStart will fill it.
            elif name in self.servers:
                raise Mark2Error("server already running: %s" % name)

        self.server_name = name

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


class CommandTyTerminal(CommandTySelective):
    options_spec = (
        ('wait', ('-w', '--wait'), 'REGEX', 'wait for this line of output to appear on console before returning.'),
        ('only', ('-o', '--only'), '',      'print the matched line and no others'),
        ('immediate', ('-i', '--immediate'), '', 'don\'t wait for any output'))

    wait = None
    wait_from_start = False
    only = False
    def do_end(self):
        if 'wait' in self.options:
            self.wait = self.options['wait']
        if 'only' in self.options:
            self.only = True
        if 'immediate' in self.options:
            self.wait = None

        try:
            self.do_wait()
        except KeyboardInterrupt:
            pass

    def do_wait(self):
        if self.wait is None:
            return
        while not os.path.exists(self.shared('log')):
            time.sleep(0.1)
        with open(self.shared('log'), 'r') as f:
            if not self.wait_from_start:
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
                    if re.search(self.wait, line2[2]):
                        print line[3]
                        return
                    elif not self.only:
                        print line[3]


class CommandHelp(Command):
    """display help and available options"""
    name = 'help'
    value_spec = "[COMMAND]"
    def run(self):
        if self.value is None:
            print help_text.format(
                usage=usage_text,
                commands=self.columns([(c.name, c.value_spec, c.__doc__) for c in commands]))
        elif self.value in commands_d:
            cls = commands_d[self.value]
            print help_sub_text.format(
                subcommand = self.value,
                doc = cls.__doc__,
                value_spec = cls.value_spec
            )
            opts = cls.get_options_spec()
            if len(opts) > 0:
                print "options:"
                print self.columns([(' '.join(o[1]), o[2], o[3]) for o in opts]) + "\n"
        else:
            raise Mark2Error("Unknown command: %s" % self.value)

    def columns(self, data):
        o = []
        for tokens in data:
            line = ""
            for i, token in enumerate(tokens):
                line += token
                line += " "*(((i+1)*12)-len(line))
            o.append(line)

        return "\n".join(("  "+l for l in o))


class CommandStart(CommandTyTerminal):
    """start a server"""
    name = 'start'
    value_spec='[PATH]'
    name_should_exist = False

    def get_server_path(self):
        self.jar_file = None
        self.server_path = os.path.realpath("" if self.value is None else self.value)

        if os.path.isdir(self.server_path):
            pass
        elif os.path.isfile(self.server_path):
            if self.server_path.endswith('.jar'):
                self.server_path, self.jar_file = os.path.split(self.server_path)
            else:
                raise Mark2Error("unknown file type: " + self.server_path)
        else:
            raise Mark2Error("path does not exist: " + self.server_path)

    @staticmethod
    def get_umask():
        cu = os.umask(0)
        os.umask(cu)
        return "{0:03o}".format(cu)

    def check_ownership(self):
        d_user = pwd.getpwuid(os.stat(self.server_path).st_uid).pw_name
        m_user = getpass.getuser()
        if d_user != m_user:
            e = "server directory is owned by '{d_user}', but mark2 is running as '{m_user}'. " + \
                "please start mark2 as `sudo -u {d_user} mark2 start ...`"
            raise Mark2Error(e.format(d_user=d_user,m_user=m_user))

    def check_executable(self, cmd):
        return subprocess.call(
            ["type", cmd],
            shell = True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        ) == 0

    def copy_config(self, src, dest, header=''):
        f0 = open(src,  'r')
        f1 = open(dest, 'w')
        l0 = ''

        while l0.strip() == '' or l0.startswith('### ###'):
            l0 = f0.readline()

        f1.write(header)

        while l0 != '':
            f1.write(l0)
            l0 = f0.readline()

        f0.close()
        f1.close()

    def diff_config(self, src, dest):
        diff = ""

        with open(src, 'r') as f0:
            d0 = f0.readlines()
        with open(dest,'r') as f1:
            d1 = f1.readlines()

        import difflib
        ignore = " \t\f\r\n"
        s = difflib.SequenceMatcher(lambda x: x in ignore, d0, d1)
        for tag, i0, i1, j0, j1 in s.get_opcodes():
            if tag in ('replace', 'insert'):
                for l1 in d1[j0:j1]:
                    if l1.strip(ignore) != '':
                        diff += l1

        return diff

    def check_config(self):
        path_old = 'resources/mark2.default.properties'
        path_new = 'config/mark2.properties'

        def write_config(data=''):
            data = "# see resources/mark2.default.properties for details\n" + data
            with open(path_new, 'w') as file_new:
                file_new.write(data)

        #exit 1: already configured
        if os.path.exists(path_new):
            return

        self.make_writable('config')

        #exit 2: no editor
        if not self.check_executable("editor"):
            return write_config()

        #exit 3: user intervention
        print "mark2 is unconfigured!"
        response = raw_input('would you like to configure it now [yes]? ') or 'yes'
        if response != 'yes':
            return write_config()

        #launch our editor
        fd_tmp, path_tmp = tempfile.mkstemp(prefix='mark2.properties.', text=True)
        self.copy_config(path_old, path_tmp)
        subprocess.call(['editor', path_tmp])

        #diff the files
        write_config(self.diff_config(path_old, path_tmp))
        os.remove(path_tmp)


    def get_env(self):
        env = dict(os.environ)
        pp = env.get('PYTHONPATH', '')
        if len(pp) > 0:
            env['PYTHONPATH'] = self.script_path + os.pathsep + pp
        else:
            env['PYTHONPATH'] = self.script_path
        return env

    def run(self):
        # parse the server path
        self.get_server_path()

        # get server name
        if self.server_name is None:
            self.server_name = os.path.basename(self.server_path)
            if self.server_name in self.servers:
                raise Mark2Error("server already running: %s" % self.server_name)

        # move to the directory this script is in
        os.chdir(os.path.realpath(self.script_path))

        # check we've got config/mark2.properties
        self.check_config()

        # check we own the server dir
        self.check_ownership()

        # clear old stuff
        for x in ('log', 'sock', 'pid'):
            if os.path.exists(self.shared(x)):
                os.remove(self.shared(x))

        i = 1
        while True:
            p = self.shared("log.%d" % i)
            if not os.path.exists(p):
                break
            os.remove(p)
            i += 1

        # build command
        command = [
            'twistd',
            '--pidfile', self.shared('pid'),
            '--logfile', '/dev/null',
            '--umask', self.get_umask(),
            'mark2',
            '--shared-path', self.shared_path,
            '--server-name', self.server_name,
            '--server-path', self.server_path]

        if self.jar_file:
            command += ['--jar-file', self.jar_file]

        # start twistd
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.get_env())
        stderr = process.communicate()[1].strip()
        if stderr != '':
            print stderr
            raise Mark2Error("twistd failed to start up!")

        self.wait = '# mark2 started|stopped\.'
        self.wait_from_start = True

class CommandList(CommandTyStateful):
    """list running servers"""
    name = 'list'
    def run(self):
        for s in self.servers:
            print s


class CommandAttach(CommandTySelective):
    """attach to a server"""
    name = 'attach'
    def run(self):
        os.chdir(self.script_path)
        f = user_client.UserClientFactory(self.server_name, self.shared_path)
        f.main()


class CommandStop(CommandTyTerminal):
    """stop mark2"""
    name = 'stop'
    def run(self):
        self.do_send('~stop')
        self.wait='# mark2 stopped\.'


class CommandKill(CommandTyTerminal):
    """kill mark2"""
    name = 'kill'
    def run(self):
        self.do_send('~kill')
        self.wait = '# mark2 stopped\.'


class CommandSend(CommandTyTerminal):
    """send a console command"""
    name = 'send'
    value_spec='INPUT...'
    def run(self):
        if self.value is None:
            raise Mark2ParseError("nothing to send!")
        self.do_send(self.value)


class CommandJarList(Command):
    """list server jars"""
    name = 'jar-list'
    def run(self):
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


class CommandJarGet(Command):
    """download a server jar"""
    name = 'jar-get'
    value_spec='NAME'
    def run(self):
        if self.value is None:
            raise Mark2ParseError("missing jar type!")

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

        d = servers.jar_get(self.value)
        d.addCallbacks(handle, err)
        reactor.run()


commands = (CommandHelp, CommandStart, CommandList, CommandAttach, CommandStop, CommandKill, CommandSend, CommandJarList, CommandJarGet)
commands_d = dict([(c.name, c) for c in commands])


def main(argv):
    c_args = argv[1:]
    if len(c_args) == 0:
        command_name = 'help'
    else:
        command_name = c_args.pop(0)
    command_cls = commands_d.get(command_name, None)
    if command_cls is None:
        raise Mark2ParseError("unknown command: %s" % command_name)
    command = command_cls()

    command.parse_options(c_args)
    command.start()
