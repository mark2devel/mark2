from plugins import Plugin
from events import Hook, ServerStop, StatPlayers


class Shutdown(Plugin):
    warn_delay = 60
    soft_timeout  = 60 #How long to wait for the server to stop gracefully
    
    failsafe = None
    
    def setup(self):
        self.players = []
        
        self.register(self.handle_players, StatPlayers)
        
        self.register(self.h_restart,       Hook, public=True, name="restart",      doc='attempts to cleanly restart the server; after a timeout kills it and brings it back')
        self.register(self.h_restart_warn,  Hook, public=True, name="restart-warn", doc='announce a restart in chat, then restart n seconds later')
        self.register(self.h_restart_kill,  Hook, public=True, name="restart-kill", doc='kill the server and bring it back up')
        self.register(self.h_stop,          Hook, public=True, name="stop",         doc='attempts to cleanly stop the server; after a timeout kills it')
        self.register(self.h_stop_warn,     Hook, public=True, name="stop-warn",    doc='announce a shutdown in chat, then stop n seconds later')
        self.register(self.h_stop_kill,     Hook, public=True, name="stop-kill",    doc='kill the server')
        
    def handle_players(self, event):
        self.players = event.players
    
    def nice_stop(self, message, respawn, kill):
        if not kill:
            self.send('save-all')
            for player in self.players:
                self.send('kick %s %s' % (player, message))
        self.dispatch(ServerStop(reason='console', respawn=respawn, kill=kill))
    
    #Hook handlers:
    def h_restart(self, event):
        self.nice_stop('Server restarting.', True, False)
    
    def h_restart_kill(self, event):
        self.nice_stop('Server restarting.', True, True)
    
    def h_restart_warn(self, event):
        self.send('say RESTARTING IN %d SECONDS.' % self.warn_delay)
        self.send('say ALL PROGRESS WILL BE SAVED.')
        self.delayed_task(self.h_restart, self.warn_delay)
    
    def h_stop(self, event):
        self.nice_stop('Server going down for maintainence.', False, False)
    
    def h_stop_kill(self, event):
        self.nice_stop('Server going down for maintainence.', False, True)
    
    def h_stop_warn(self, event):
        self.send("say SERVER GOING DOWN FOR MAINTENANCE IN %d SECONDS." % self.warn_delay)
        self.send('say ALL PROGRESS WILL BE SAVED.')
        self.delayed_task(self.h_stop, self.warn_delay)
    
