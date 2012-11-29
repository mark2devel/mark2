import time
import gzip
import os

from plugins import Plugin, ConsoleInterest, ShutdownTask, register


class Log(Plugin):
    gzip      = True
    path      = "logs/server-{timestamp}-{status}.log.gz"
    
    log = ""
    
    def setup(self):
        self.register(self.logger, Console)
        self.register(self.shutdown, ServerStopped)
    
    def logger(self, event):
        self.log += event.line + "\n"
    
    @register(ShutdownTask)
    def shutdown(self, event):
        reason = event.reason
        if reason == None:
            reason = "ok"
            
        timestamp = time.strftime("%Y-%m-%d-%H:%M:%S", time.gmtime())
        
        path = self.path.format(timestamp=timestamp, name=self.parent.name, status=reason)

        if not os.path.exists(os.path.dirname(path)):
            try:
                os.makedirs(os.path.dirname(path))
            except IOError:
                self.console("Warning: {} does't exist and I can't create it".format(os.path.dirname(path)),
                             kind='error')
                return
        
        if self.gzip:
            f = gzip.open(path, 'wb')
        else:
            f = open(path, 'w')
        
        f.write(self.log)
        f.close()
        self.console("server.log written to %s" % os.path.realpath(path))
        self.log = ""
