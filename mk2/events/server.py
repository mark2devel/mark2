import re

from . import Event, get_timestamp

# input/output
output_exp = re.compile(
        r'^(?:\W|\[1G|\[K|)+(?:\d{4}-\d{2}-\d{2} |)\[?(\d{2}:\d{2}:\d{2})\]? \[?(?:[^\]]+?/|)([A-Z]+)\]:?\s*(.*)')

class ServerInput(Event):
    """Send data to the server's stdin. In plugins, a shortcut
    is available: self.send("say hello")"""
    
    line         = Event.Arg(required=True)


class ServerOutput(Event):
    """Issued when the server gives us a line on stdout. Note
    that to handle this, you must specify both the 'level'
    (e.g. INFO or SEVERE) and a regex pattern to match"""
    
    line  = Event.Arg(required=True)
    time  = Event.Arg()
    level = Event.Arg()
    data  = Event.Arg()
    
    def setup(self):
        m = output_exp.match(self.line)
        if m:
            g = m.groups()
            self.time = g[0]
            self.level= g[1]
            self.data = g[2]
        else:
            self.level= "RAW"
            self.data = self.line
        
        self.time = get_timestamp(self.time)
    
    def prefilter(self, pattern, level=None):
        if level and level != self.level:
            return False
        
        m = re.match(pattern, self.data.strip())
        if not m:
            return False
        
        self.match = m
        
        return True
    
# start


class ServerStart(Event):
    """Issue this event to start the server"""
    
    pass


class ServerStarting(Event):
    """Issued by the ServerStart handler to alert listening plugins
    that the server process has started"""
    
    pid = Event.Arg()


class ServerStarted(Event):
    """Issued when we see the "Done! (1.23s)" line from the server
    
    This event has a helper method in plugins - just overwrite
    the server_started method.
    """

class ServerStop(Event):
    """Issue this event to stop the server."""
    
    TERMINATE = 0
    RESTART = 1
    HOLD = 2
    
    reason   = Event.Arg(required=True)
    respawn  = Event.Arg(required=True)
    kill     = Event.Arg(default=False)
    announce = Event.Arg(default=True)

    dispatch_once = True


class ServerStopping(Event):
    """Issued by the ServerStop handler to alert listening plugins
    that the server is going for a shutdown
    
    This event has a helper method in plugins - just overwrite
    the server_started method."""

    reason  = Event.Arg(required=True)
    respawn = Event.Arg(required=True)
    kill    = Event.Arg(default=False)


class ServerStopped(Event):
    """When the server process finally dies, this event is raised"""
    pass


class ServerEvent(Event):
    """Tell plugins about something happening to the server"""

    cause    = Event.Arg(required=True)
    friendly = Event.Arg()
    data     = Event.Arg(required=True)
    priority = Event.Arg(default=0)
    
    def setup(self):
        if not self.friendly:
            self.friendly = self.cause
