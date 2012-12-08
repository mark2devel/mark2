import time
import tarfile
import glob
import os

from plugins import Plugin
from events import ServerStopped


class Backup(Plugin):
    path = "backups/{timestamp}.tar.gz"
    mode = "include"
    spec = "world*"
    
    def setup(self):
        self.register(self.shutdown, ServerStopped)
    
    def shutdown(self, event):
        timestamp = time.strftime("%Y-%m-%d-%H:%M:%S", time.gmtime())
        path = self.path.format(timestamp=timestamp, name=self.parent.name)
        if not os.path.exists(os.path.dirname(path)):
            try:
                os.makedirs(os.path.dirname(path))
            except IOError:
                self.console("Warning: {} does't exist and I can't create it".format(os.path.dirname(path)),
                             kind='error')
                return
        tar = tarfile.open(path, "w:gz")
        
        add = set()
        if self.mode == "include":
            for e in self.spec.split(";"):
                add |= set(glob.glob(e))
        elif self.mode == "exclude":
            add += set(glob.glob('*'))
            for e in self.spec.split(";"):
                add -= set(glob.glob(e))
        
        for a in add:
            tar.add(a)
       
        tar.close()
        self.console("map data backed up to %s" % os.path.realpath(path))
