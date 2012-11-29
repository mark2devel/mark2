from plugins import Plugin
from events import ACCEPTED, FINISHED

class HangChecker(Plugin):
    crash_enabled     = True
    crash_interval    = 60
    crash_fail_limit  = 10
    
    oom_enabled       = True
    
    ping_enabled      = True
    ping_fail_limit   = 10

    pcount_enabled    = False
    pcount_interval   = 60
    pcount_fail_limit = 10

    
    def setup(self):
        if self.oom_enabled:
            self.register(self.handle_oom, ServerOutput, level='SEVERE', pattern='java\.lang\.OutOfMemoryError.*')
        
        if self.ping_enabled:
            self.register(self.handle_ping, StatPlayerCount)
        
        if self.pcount_enabled:
            self.register(self.handle_pcount, StatPlayerCount)
   
    def server_started(self, event):
        self.reset_counts()
        if self.crash_enabled:
            self.repeating_task(self.crash_loop, self.crash_interval)
            
        if self.ping_enabled:
            self.repeating_task(self.ping_loop, self.config['mark2.services.ping.interval'])
        
        if self.pcount_enabled:
            self.repeating_task(self.pcount_loop, self.pcount_interval)
    
    def reset_counts(self, event):
        self.crash_alive  = True
        self.crash_fails  = 0
        self.ping_alive   = True
        self.ping_fails   = 0
        self.pcount_alive = True
        self.pcount_fails = 0
    
    
    ### loops

    # crash
    def crash_loop(self):
        if not self.crash_alive:
            self.crash_fails += 1
            self.console('server might have crashed! check %d of %d' % (self.crash_fails, self.crash_fail_limit))
            if self.crash_fails == self.crash_fail_limit:
                self.console('server has crashed, restarting...')
                self.dispatch(ServerStop(reason='crashed', respawn=True))
        
        self.crash_alive = False
        self.register(self.handle_crash_ok, ServerOutputConsumer, pattern='Unknown command.*')
        self.send('') # Blank command to trigger 'Unknown command'

    # ping
    def ping_loop(self):
        if not self.ping_alive:
            self.ping_fails += 1
            self.console('server might have stopped accepting connections! check %d of %d' % (self.ping_fails, self.ping_fail_limit))
            if self.ping_fails == self.ping_fail_limit:
                self.console('server has stopped accepting connections, restarting...')
                self.dispatch(ServerStop(reason='not accepting connections', respawn=True))
    
    #pcount
    def pcount_loop(self):
        if not self.pcount_alive:
            self.pcount_fails += 1
            self.console('server has 0 players on! check %d of %d' % (self.pcount_fails, self.pcount_fail_limit))
            if self.pcount_fails == self.pcount_fail_limit:
                self.console('server has had 0 players for ages - something is awry. restarting...')
                self.dispatch(ServerStop(reason='zero playes', respawn=True))
    
    ### handlers
    
    # crash
    def handle_crash_ok(self, event):
        self.crash_fails = 0
        self.crash_alive = True
        return ACCEPTED | FINISHED
    
    # out of memory
    def handle_oom(self, event):
        self.console('server out of memory, restarting...')
        self.dispatch(ServerStop(reason='out of memory', respawn=True))

    # ping
    def handle_ping(self, event):
        if event.source='ping':
            self.ping_fails = 0
            self.ping_alive = True
    
    # pcount
    def handle_pcount(self, event):
        if event.player_count > 0:
            self.pcount_fails = 0
            self.pcount_alive = True
