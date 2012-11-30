from plugins import Plugin
from events import Hook, ServerStop, ServerStopping, ServerStopped, ServerSave, ServerKill


class Shutdown(Plugin):
    warn_delay = 60
    soft_timeout  = 60 #How long to wait for the server to stop gracefully
    
    failsafe = None
    
    def setup(self):
        self.register(self.stop_server,    ServerStop)
        self.register(self.server_stopped, ServerStopped)
        
        self.register(self.h_restart,       Hook, public=True, name="restart",      doc='calls ~restart-soft, and will call ~restart-hard a little later if the server won\'t die')
        self.register(self.h_restart_warn,  Hook, public=True, name="restart-warn", doc='runs /say to announce a restart and schedules a ~restart-soft')
        self.register(self.h_restart_soft,  Hook, public=True, name="restart-soft", doc='runs /save-all and /stop, brings it back up')
        self.register(self.h_restart_hard,  Hook, public=True, name="restart-hard", doc='kills a hung server and brings it back up')
        self.register(self.h_stop,          Hook, public=True, name="stop",         doc='calls ~stop-soft, and will call ~stop-hard a little later if the server won\'t die')
        self.register(self.h_stop_warn,     Hook, public=True, name="stop-warn",    doc='runs /say to announce a stop and schedules a ~stop-soft')
        self.register(self.h_stop_warn,     Hook, public=True, name="stop-soft",    doc='runs /save-all and /stop')
        self.register(self.h_stop_warn,     Hook, public=True, name="stop-hard",    doc='kills a hung server')
        

    def stop_server(self, event):
        self.both(event.respawn)
        self.dispatch(ServerStopping(reason=event.reason, respawn=event.respawn))
        event.handled = True
    
    def server_stopping(self, event):
        pass
        
    def server_stopped(self, event):
        if self.failsafe:
            self.failsafe.cancel()
            self.failsafe = None
    
    def warn(self, resurrect):
        if resurrect:
            self.send('say RESTARTING IN %d SECONDS.' % self.warn_delay)
        else:
            self.send("say SERVER GOING DOWN FOR MAINTENANCE IN %d SECONDS." % self.warn_delay)
        self.send('say ALL PROGRESS WILL BE SAVED.')
        
        self.delayed_task(lambda: self.soft(resurrect), self.warn_delay)
    
    def soft(self, resurrect):
        self.parent.resurrect = resurrect
        
        message = {
            False: 'Server going down for maintainence.',
            True:  'Server restarting.'}
        self.dispatch(ServerSave())
        self.send('kickall %s' % message[resurrect])
        self.send('stop')
    
    def hard(self, resurrect):
        self.parent.resurrect = resurrect
        if self.parent.failure == None:
            self.parent.failure == 'wontstop'
        self.kill_process()
    
    def both(self, resurrect):
        self.parent.resurrect = resurrect
        self.soft(resurrect)
        self.failsafe = self.delayed_task(lambda: self.hard(resurrect), self.soft_timeout)
    
    #Hook handlers:
    
    def h_restart(self, event):
        self.both(True)
    def h_restart_warn(self, event):
        self.warn(True)
    def h_restart_soft(self, event):
        self.soft(True)
    def h_restart_hard(self, event):
        self.hard(True)
    
    def h_stop(self, event):
        self.both(False)
    def h_stop_warn(self, event):
        self.warn(False)
    def h_stop_soft(self, event):
        self.soft(False)
    def h_stop_hard(self, event):
        self.hard(False)
