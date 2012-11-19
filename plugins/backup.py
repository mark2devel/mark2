import time
import tarfile
import glob
import os

from plugins import Plugin, ShutdownTask, register


class Backup(Plugin):
    path = "backups/{timestamp}.tar.gz"
    
    @register(ShutdownTask)
    def shutdown(self, reason):
        timestamp = time.strftime("%Y-%m-%d-%H:%M:%S", time.gmtime())
        path = self.path.format(timestamp=timestamp, name=self.parent.name)
        tar = tarfile.open(path, "w:gz")
        for world in glob.glob("world*"):
            tar.add(world)
        tar.close()
        self.console("map data backed up to %s" % os.path.realpath(path))
