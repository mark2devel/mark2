import re

from events import Event, get_timestamp, ACCEPTED, FINISHED

# input/output

class ServerInput(Event):
    """Send data to the server's stdin. In plugins, a shortcut
    is available: self.send("say hello")"""
    
    requires = ('line',)
    parse_colors = False
    def setup(self):
        if self.parse_colors:
            self.line = re.sub("\&([0-9a-fklmnor])", u"\u00a7\\1", self.line, flags=re.IGNORECASE)

class ServerOutput(Event):
    """Issued when the server gives us a line on stdout. Note
    that to handle this, you must specify both the 'level'
    (e.g. INFO or SEVERE) and a regex pattern to match"""
    
    contains = ('line', 'time', 'level', 'data')
    requires = ('line',)
    requires_predicate = ('pattern',)
    
    data = None
    time = None
    
    
    def setup(self):
        m = re.match(r'(\d{4}-\d{2}-\d{2} |)(\d{2}:\d{2}:\d{2}) \[([A-Z]+)\] (?:\[Minecraft\] )?(.*)', self.line)
        if m:
            g = m.groups()
            self.time = g[0]+g[1]
            self.level= g[2]
            self.data = g[3]
        else:
            self.level= "???"
            self.data = self.line.strip()
        
        self.time = get_timestamp(self.time)
    
    def consider(self, d):
        if 'level' in d and d['level'] != self.level:
            return 0
        
        m = re.match(d['pattern'], self.data)
        if not m:
            return 0
        
        self.match = m
        
        r = ACCEPTED
        if d.get('once', False):
            r |= FINISHED
        
        return r

class ServerOutputConsumer(ServerOutput):
    """Issued prior to the ServerOutput handlers seeing it. Takes
    the same handler parameters as ServerOutput. In most cases
    you shouldn't specify a callback"""
    
    pass
    
# start

class ServerStart(Event):
    """Issue this event to start the server"""
    
    pass

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
    contains=('reason', 'respawn', 'kill', 'announce')
    requires=('reason', 'respawn')
    kill=False
    announce=True #generate a ServerStopping event

class ServerStopping(Event):
    """Issued by the ServerStop handler to alert listening plugins
    that the server is going for a shutdown
    
    This event has a helper method in plugins - just overwrite
    the server_started method."""
    
    contains=('reason', 'respawn', 'kill')
    requires=('reason', 'respawn')
    kill=False

class ServerStopped(Event):
    """When the server process finally dies, this event is raised"""
    pass
