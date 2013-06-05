import time
import gzip
import os
import re

from mk2.plugins import Plugin
from mk2.events import Console, ServerStopped, ServerStopping, ServerOutput


class Log(Plugin):
    gzip      = Plugin.Property(default=True)
    path      = Plugin.Property(default="logs/server-{timestamp}-{status}.log.gz")
    vanilla   = Plugin.Property(default=False)
    
    log = u""
    reason = "unknown"
    time_re = re.compile(r'(?:\d{2}:\d{2}:\d{2}) (.*)')

    restore = ('log',)
    
    def setup(self):
        if self.vanilla:
            self.register(self.vanilla_logger, ServerOutput, pattern='.*')
        else:
            self.register(self.logger, Console)
        self.register(self.shutdown, ServerStopped)
        self.register(self.pre_shutdown, ServerStopping)

    def vanilla_logger(self, event):
        m = self.time_re.match(event.line)
        if m:
            self.log += u"{0} {1}\n".format(event.time, m.group(1))
        else:
            self.log += u"{0}\n".format(event.line)
    
    def logger(self, event):
        self.log += u"{0}\n".format(event.value())
    
    def pre_shutdown(self, event):
        self.reason = event.reason
    
    def shutdown(self, event):
        reason = self.reason
        if reason == None:
            reason = "ok"
            
        timestamp = time.strftime("%Y-%m-%d-%H:%M:%S", time.gmtime())
        
        path = self.path.format(timestamp=timestamp, name=self.parent.name, status=reason)

        if not os.path.exists(os.path.dirname(path)):
            try:
                os.makedirs(os.path.dirname(path))
            except IOError:
                self.console("Warning: {0} does't exist and I can't create it".format(os.path.dirname(path)),
                             kind='error')
                return
        
        if self.gzip:
            f = gzip.open(path, 'wb')
        else:
            f = open(path, 'w')
        
        f.write(self.log.encode('utf8'))
        f.close()
        self.console("server.log written to %s" % os.path.realpath(path))
        self.log = ""
