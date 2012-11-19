import time
import gzip
import os

from plugins import Plugin, ConsoleInterest, ShutdownTask, register


class Log(Plugin):
    gzip      = True
    path      = "logs/server-{timestamp}-{status}.log.gz"
    
    log = ""
    
    @register(ConsoleInterest)
    def logger(self, line):
        self.log += line + "\n"
    
    @register(ShutdownTask)
    def shutdown(self, reason):
        if reason == None:
            reason = "ok"
            
        timestamp = time.strftime("%Y-%m-%d-%H:%M:%S", time.gmtime())
        
        path = self.path.format(timestamp=timestamp, name=self.parent.name, status=reason)
        
        if self.gzip:
            f = gzip.open(path, 'wb')
        else:
            f = open(path, 'w')
        
        f.write(self.log)
        f.close()
        self.console("server.log written to %s" % os.path.realpath(path))
        self.log = ""
