from events import Event

# input/output

class ServerInput(Event):
    """Send data to the server's stdin. In plugins, a shortcut
    is available: self.send("say hello")"""
    
    requires = ['line']

class ServerOutput(Event):
    """Issued when the server gives us a line on stdout. Note
    that to handle this, you must specify both the 'level'
    (e.g. INFO or SEVERE) and a regex pattern to match"""
    
    requires = ['line']
    
    mc_line = '^(?:\d{4}-\d{2}-\d{2} )?\d{2}:\d{2}:\d{2} \[{level}\] {pattern}$'
    
    def consider(self, r_args):
        return self.extra(r_args) != {}
    
    def extra(self, r_args):
        return {'match': re.match(self.mc_line.format(r_args), self.line)}

class ServerOutputConsumer(ServerOutput):
    """Issued prior to the ServerOutput handlers seeing it. Takes
    the same handler parameters as ServerOutput. In most cases
    you shouldn't specify a callback"""
    
    handle_once = True
    dispatch_once = True
    requires = ['line']

# start

class ServerStart(Event):
    """Issue this event to start the server"""
    
    dispatch_once = True

class ServerStarting(Event):
    """Issued by the ServerStart handler to alert listening plugins
    that the server process has started"""
    
    pass

class ServerStarted(Event)
    """Issued when we see the "Done! (1.23s)" line from the server
    
    This event has a helper method in plugins - just overwrite
    the server_started method.
    """
    
    pass

#stop

class ServerStop(Event):
    """Issue this event to stop the server."""
    
    dispatch_once = True
    requires=['reason', 'respawn']

class ServerStopping(Event):
    """Issued by the ServerStop handler to alert listening plugins
    that the server is going for a shutdown
    
    This event has a helper method in plugins - just overwrite
    the server_started method."""
    
    requires=['reason']

class ServerStopped(Event):
    """When the server process finally dies, this event is raised"""
    
    pass
