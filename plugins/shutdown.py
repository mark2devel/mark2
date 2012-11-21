from plugins import Plugin, Command, ShutdownTask


class Shutdown(Plugin):
    repeat          = True
    repeat_interval = 30
    warn_delay = 60
    soft_timeout  = 60 #How long to wait for the server to stop gracefully
    
    failsafe = None
    
    def setup(self):
        self.restart      = lambda *a: self.both(True)
        self.warn_restart = lambda *a: self.warn(True)
        self.soft_restart = lambda *a: self.soft(True)
        self.hard_restart = lambda *a: self.hard(True)
        self.stop         = lambda *a: self.both(False)
        self.warn_stop    = lambda *a: self.warn(False)
        self.soft_stop    = lambda *a: self.soft(False)
        self.hard_stop    = lambda *a: self.hard(False)
        
        
        self.register(Command(self.restart,      'restart', 'calls ~restart-soft, and will call ~restart-hard a little later if the server won\'t die'))
        self.register(Command(self.warn_restart, 'restart-warn', 'runs /say to announce a restart and schedules a ~restart-soft'))
        self.register(Command(self.soft_restart, 'restart-soft', 'runs /save-all and /stop, brings it back up'))
        self.register(Command(self.hard_restart, 'restart-hard', 'kills a hung server and brings it back up'))
        self.register(Command(self.stop,         'stop', 'calls ~stop-soft, and will call ~stop-hard a little later if the server won\'t die'))
        self.register(Command(self.warn_stop,    'stop-warn', 'runs /say to announce a stop and schedules a ~stop-soft'))
        self.register(Command(self.soft_stop,    'stop-soft', 'runs /save-all and /stop'))
        self.register(Command(self.hard_stop,    'stop-hard', 'kills a hung server'))
        
        self.register(ShutdownTask(self.server_stopped))
        if self.repeat:
            self.repeating_task(self.warn_restart, self.repeat_interval - self.warn_delay)

    def server_stopped(self, reason):
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
        self.plugins['save'].save()
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
