import re

from events import Event, get_timestamp, ACCEPTED

from twisted.python import log

# input/output

class ServerInput(Event):
    """Send data to the server's stdin. In plugins, a shortcut
    is available: self.send("say hello")"""
    
    requires = ('line',)

class ServerOutput(Event):
    """Issued when the server gives us a line on stdout. Note
    that to handle this, you must specify both the 'level'
    (e.g. INFO or SEVERE) and a regex pattern to match"""
    
    requires = ('line',)
    requires_predicate = ('pattern',)
    
    data = None
    time = None
    
    def setup(self):
        log.msg(self.line)
        m = re.match('(\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2}) \[([A-Z]+)\] (.*)', self.line)
        if m:
            g = m.groups()
            self.time = g[0]+g[1]
            self.level= g[2]
            self.data = g[3]
        else:
            self.level= "UNKNOWN"
            self.data = self.line.strip()
        
        self.time = get_timestamp(self.time)
    
    def consider(self, r_args):
        d = {'level': 'INFO'}
        d.update(r_args)
        
        if self.level != d['level']:
            return 0
        
        m = re.match(d['pattern'], self.data)
        if not m:
            return 0
        
        self.match = m
        return ACCEPTED

class ServerOutputConsumer(ServerOutput):
    """Issued prior to the ServerOutput handlers seeing it. Takes
    the same handler parameters as ServerOutput. In most cases
    you shouldn't specify a callback"""
    
    requires = ('line',)

# start

class ServerStart(Event):
    """Issue this event to start the server"""
    
    dispatch_once = True

class ServerStarting(Event):
    """Issued by the ServerStart handler to alert listening plugins
    that the server process has started"""
    
    pass

class ServerStarted(Event):
    """Issued when we see the "Done! (1.23s)" line from the server
    
    This event has a helper method in plugins - just overwrite
    the server_started method.
    """
    
    pass

#stop

class ServerStop(Event):
    """Issue this event to stop the server."""
    
    dispatch_once = True
    requires=('reason', 'respawn')
    kill=False
    announce=True #generate a ServerStopping event

class ServerStopping(Event):
    """Issued by the ServerStop handler to alert listening plugins
    that the server is going for a shutdown
    
    This event has a helper method in plugins - just overwrite
    the server_started method."""
    
    requires=('reason', 'respawn')

class ServerStopped(Event):
    """When the server process finally dies, this event is raised"""
    pass

#other

class ServerSave(Event):
    """Issue this event to save."""
    pass
