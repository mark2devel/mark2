from mk2.plugins import Plugin
from mk2.events import Hook, ServerStop, ServerStart, StatPlayers, StatPlayerCount


class Shutdown(Plugin):
    restart_warn_message   = Plugin.Property(default="WARNING: planned restart in {delay}.")
    stop_warn_message      = Plugin.Property(default="WARNING: server going down for planned maintainence in {delay}.")
    restart_message        = Plugin.Property(default="Server restarting.")
    stop_message           = Plugin.Property(default="Server going down for maintainence.")
    restart_cancel_message = Plugin.Property(default="WARNING: planned restart cancelled.")
    restart_cancel_reason  = Plugin.Property(default="WARNING: planned restart cancelled ({reason}).")
    stop_cancel_message    = Plugin.Property(default="WARNING: planned maintenance cancelled.")
    stop_cancel_reason     = Plugin.Property(default="WARNING: planned maintenance cancelled ({reason}).")
    alert_command          = Plugin.Property(default="say %s")
    kick_command           = Plugin.Property(default="kick {player} {message}")
    kick_mode              = Plugin.Property(default="all")
    
    failsafe = None

    cancel_preempt = 0

    restart_on_empty = False

    restore = ('cancel_preempt', 'cancel', 'restart_on_empty')
    
    def setup(self):
        self.players = []
        self.cancel = []
        
        self.register(self.handle_players, StatPlayers)
        self.register(self.handle_player_count, StatPlayerCount)
        
        self.register(self.h_stop,          Hook, public=True, name="stop",         doc='cleanly stop the server and terminate the wrapper. specify a delay like `~stop 2m`')
        self.register(self.h_restart,       Hook, public=True, name="restart",      doc='cleanly restart the server. specify a delay like `~restart 30s`')
        self.register(self.h_restart_empty, Hook, public=True, name="restart-empty",doc='restart the server next time it has 0 players')
        self.register(self.h_hold,          Hook, public=True, name="hold",         doc='cleanly stop the server, but do not terminate the wrapper. specify a delay like `~hold 2m`')
        self.register(self.h_kill,          Hook, public=True, name="kill",         doc='kill the server and terminate the wrapper')
        self.register(self.h_kill_restart,  Hook, public=True, name="kill-restart", doc='kill the server and bring it back up')
        self.register(self.h_kill_hold,     Hook, public=True, name="kill-hold",    doc='kill the server, but do not terminate the wrapper')
        self.register(self.h_cancel,        Hook, public=True, name="cancel",       doc='cancel an upcoming shutdown or restart')
        self.register(self.h_unhold,        Hook, public=True, name="unhold",       doc='unhold the server after it has been held before')

    def server_started(self, event):
        self.restart_on_empty = False
        self.cancel_preempt = 0
    
    def warn_restart(self, delay):
        self.send_format(self.alert_command % self.restart_warn_message, delay=delay)
    
    def warn_stop(self, delay):
        self.send_format(self.alert_command % self.stop_warn_message, delay=delay)

    def warn_cancel(self, reason, thing):
        if reason:
            message = self.restart_cancel_reason if thing == "restart" else self.stop_cancel_reason
        else:
            message = self.restart_cancel_message if thing == "restart" else self.stop_cancel_message
        self.send_format(self.alert_command % message, reason=reason)

    def nice_stop(self, respawn, kill):
        if not kill:
            message = self.restart_message if respawn else self.stop_message
            if self.kick_mode == 'all':
                for player in self.players:
                    self.send_format(self.kick_command, player=player, message=message)
            elif self.kick_mode == 'once':
                self.send_format(self.kick_command, message=message)
        self.dispatch(ServerStop(reason='console', respawn=respawn, kill=kill))

    def handle_players(self, event):
        self.players = event.players

    def handle_player_count(self, event):
        if event.players_current == 0 and self.restart_on_empty:
            self.restart_on_empty = False
            self.nice_stop(ServerStop.RESTART, False)

    def cancel_something(self, reason=None):
        thing, cancel = self.cancel.pop(0)
        cancel(reason, thing)

    def should_cancel(self):
        if self.cancel_preempt:
            self.cancel_preempt -= 1
            return True
        else:
            return False
    
    #Hook handlers:
    def h_stop(self, event=None):
        if self.should_cancel():
            self.console("I'm not stopping because this shutdown was cancelled with ~cancel")
            return
        action = lambda: self.nice_stop(ServerStop.TERMINATE, False)
        if event and event.args:
            warn_length, action, cancel = self.action_chain_cancellable(event.args, self.warn_stop, action, self.warn_cancel)
            self.cancel.append(("stop", cancel))
        action()

    def h_restart(self, event=None):
        if self.should_cancel():
            self.console("I'm not restarting because this shutdown was cancelled with ~cancel")
            return
        action = lambda: self.nice_stop(ServerStop.RESTART, False)
        if event and event.args:
            warn_length, action, cancel = self.action_chain_cancellable(event.args, self.warn_restart, action, self.warn_cancel)
            self.cancel.append(("restart", cancel))
        action()
        
    def h_hold(self, event=None):
        if self.should_cancel():
            self.console("I'm not stopping because this shutdown was cancelled with ~cancel")
            return
        action = lambda: self.nice_stop(ServerStop.HOLD, False)
        if event and event.args:
            warn_length, action, cancel = self.action_chain_cancellable(event.args, self.warn_stop, action, self.warn_cancel)
            self.cancel.append(("stop", cancel))
        action()

    def h_restart_empty(self, event):
        if self.restart_on_empty:
            self.console("I was already going to do that")
        else:
            self.console("I will restart the next time the server empties")
        self.restart_on_empty = True
    
    def h_kill(self, event):
        self.nice_stop(ServerStop.TERMINATE, True)
    
    def h_kill_restart(self, event):
        self.nice_stop(ServerStop.RESTART, True)
    
    def h_kill_hold(self, event):
        self.nice_stop(ServerStop.HOLD, True)
    
    def h_unhold(self, event):
        self.dispatch(ServerStart())

    def h_cancel(self, event):
        if self.cancel:
            self.cancel_something(event.args or None)
        else:
            self.cancel_preempt += 1
            self.console("I will cancel the next thing")
