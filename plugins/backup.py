import time
import glob
import os
from twisted.internet import protocol, reactor

from plugins import Plugin
from events import Hook
import shlex


class TarProtocol(protocol.ProcessProtocol):
    pass

class Backup(Plugin):
    path = "backups/{timestamp}.tar.gz"
    mode = "include"
    spec = "world*"
    tar_flags = '-hpczf'
    
    def setup(self):
        self.register(self.backup, Hook, public=True, name='backup', doc='backup the server to a .tar.gz')

    def backup(self, event):
        timestamp = time.strftime("%Y-%m-%d-%H:%M:%S", time.gmtime())
        path = self.path.format(timestamp=timestamp, name=self.parent.server_name)
        if not os.path.exists(os.path.dirname(path)):
            try:
                os.makedirs(os.path.dirname(path))
            except IOError:
                self.console("Warning: {} does't exist and I can't create it".format(os.path.dirname(path)),
                             kind='error')
                return

        add = set()
        if self.mode == "include":
            for e in self.spec.split(";"):
                add |= set(glob.glob(e))
        elif self.mode == "exclude":
            add += set(glob.glob('*'))
            for e in self.spec.split(";"):
                add -= set(glob.glob(e))


        cmd = ['tar']
        cmd.extend(shlex.split(self.tar_flags))
        cmd.append(path)
        cmd.extend(add)

        proto = protocol.ProcessProtocol()
        proto.processEnded = lambda reason: self.console("map backup finished!")
        proto.childDataReceived = lambda fd, d: self.console(d)

        self.console("map backup starting: %s"  % path)
        reactor.spawnProcess(proto, "/bin/tar", cmd)

