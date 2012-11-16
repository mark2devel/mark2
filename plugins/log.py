import time
import gzip
import os

from plugins import Plugin, ConsoleInterest, ShutdownTask

class Log(Plugin):
    gzip      = True
    path      = "logs/server-{timestamp}-{status}.log.gz"
    
    log = ""
    
    def setup(self):
        self.register(ConsoleInterest(self.logger))
        self.register(ShutdownTask(self.shutdown))
            

    def logger(self, line):
        self.log+=line+"\n"
    
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

ref = Log
