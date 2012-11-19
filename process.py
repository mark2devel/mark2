from twisted.internet import protocol, reactor
from twisted.application.service import Service
from itertools import chain
import os
import glob
import subprocess


class ProcessProtocol(protocol.ProcessProtocol):
    obuff = ""

    def __init__(self, parent):
        self.parent = parent

    def errReceived(self, data):
        data = data.split("\n")
        data[0] = self.obuff + data[0]
        self.obuff = data.pop()
        for l in data:
            self.parent.p_out(l)

    def processEnded(self, reason):
        self.parent.p_stop()


class ProcessService(Service):
    protocol = None

    def __init__(self, jarfile=None):
        self.jarfile = jarfile

    def startService(self):
        Service.startService(self)

        self.check_dependencies()

        self.protocol = ProcessProtocol(self.parent)

        cmd = self.build_command()
        self.process = reactor.spawnProcess(self.protocol, cmd[0], cmd)

    def stopService(self):
        Service.stopService(self)
        self.process.signalProcess('KILL')

    def check_dependencies(self):
        if os.name != 'posix':
            self.parent.fatal_error("this program requires a posix environment (linux, bsd, os x, etc)")
        if not self.check_executable('java'):
            self.parent.fatal_error("couldn't find java executable")

    def check_executable(self, name):
        return self.find_executable(name) != ''

    def find_executable(self, name):
        return subprocess.check_output(['which', name]).strip()

    def find_jar(self):
        patterns = self.parent.cfg['mark2.jar_path'].split(';')
        candidates = list(chain.from_iterable(map(glob.glob, patterns)))
        if self.jarfile:
            candidates = glob.glob(self.jarfile) + candidates
        if candidates:
            return candidates[0]
        else:
            self.parent.fatal_error("Couldn't locate a server jar!")

    def build_command(self):
        cmd = []
        cmd.append(self.find_executable('java'))
        cmd.extend(self.parent.cfg.get_jvm_options())
        cmd.append('-jar')
        cmd.append(self.find_jar())
        cmd.append('nogui')
        return cmd


def Process(parent, jarfile=None):
    service = ProcessService(jarfile)
    service.setServiceParent(parent)
    return service.protocol, service


def get_usage(pid):
    c = ['ps', '-p', str(pid), '-o', 'pcpu=', '-o', 'vsz=']
    try:
        out = subprocess.check_output(c).strip().split(" ")
    except subprocess.CalledProcessError:
        out = ("0", "0")

    return {
        'cpu': float(out[0]),
        'mem': int(out[1])
    }
