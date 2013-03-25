from plugins import Plugin
from events import Hook, ServerStop, StatPlayers


class Shutdown(Plugin):
    restart_warn_message = "WARNING: planned restart in {delay}."
    stop_warn_message    = "WARNING: server going down for planned maintainence in {delay}."
    restart_message      = "Server restarting."
    stop_message         = "Server going down for maintainence."
    kick_command         = "kick {player} {message}"
    kick_mode            = "all"
    
    failsafe = None
    
    def setup(self):
        self.players = []
        
        self.register(self.handle_players, StatPlayers)
        
        self.register(self.h_stop,          Hook, public=True, name="stop",         doc='cleanly stop the server. specify a delay like `~stop 2m`')
        self.register(self.h_restart,       Hook, public=True, name="restart",      doc='cleanly restart the server. specify a delay like `~restart 30s`')
        self.register(self.h_kill,          Hook, public=True, name="kill",         doc='kill the server')
        self.register(self.h_kill_restart,  Hook, public=True, name="kill-restart", doc='kill the server and bring it back up')
    
    def warn_restart(self, delay):
        self.send_format("say %s" % self.restart_warn_message, parseColors=True, delay=delay)
    
    def warn_stop(self, delay):
        self.send_format("say %s" % self.stop_warn_message, parseColors=True, delay=delay)

    def nice_stop(self, respawn, kill):
        if not kill:
            self.send('save-all')
            message = self.restart_message if respawn else self.stop_message
            if self.kick_mode == 'all':
                for player in self.players:
                    self.send_format(self.kick_command, player=player, message=message)
            else:
                self.send_format(self.kick_command, message=message)
        self.dispatch(ServerStop(reason='console', respawn=respawn, kill=kill))

    def handle_players(self, event):
        self.players = event.players
    
    #Hook handlers:
    def h_stop(self, event=None):
        action = lambda: self.nice_stop(False, False)
        if event and event.args:
            warn_length, action = self.action_chain(event.args, self.warn_stop, action)
        action()
    

    def h_restart(self, event=None):
        action = lambda: self.nice_stop(True, False)
        if event and event.args:
            warn_length, action = self.action_chain(event.args, self.warn_restart, action)
        action()
    
    def h_kill(self, event):
        self.nice_stop(False, True)
    
    def h_kill_restart(self, event):
        self.nice_stop(True, True)
