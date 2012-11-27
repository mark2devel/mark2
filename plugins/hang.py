from plugins import Plugin, Interest, Consumer, ShutdownTask, register

#TODO: aggressive (FE)


class HangChecker(Plugin):
    crash_enabled = True
    crash_interval = 60
    crash_fail_limit = 10
    
    oom_enabled = True
    
    ping_enabled = True
    ping_interval = 60
    ping_fail_limit = 10

    ping_pcount_enabled = False
    ping_pcount_fail_limit = 10

    
    def setup(self):
        self.reset_counts()
        self.register(self.reset_counts, ShutdownTask)
        
        if self.ping_pcount_enabled:
            self.ping_enabled = True
        
        if self.crash_enabled:
            self.repeating_task(self.crash_loop, self.crash_interval)
        
        if self.oom_enabled:
            self.register(self.handle_oom, ServerOutput, level='SEVERE', pattern='java\.lang\.OutOfMemoryError.*')
        
        if self.ping_enabled or self.pcount_enabled:
            self.register(self.handle_ping, Ping)
            if self.ping_enabled:
                self.repeating_task(self.ping_loop, self.ping_interval)
    
    def reset_counts(self, event):
        self.crash_alive  = True
        self.crash_fails  = 0
        self.ping_alive   = True
        self.ping_fails   = 0
        self.pcount_alive = True
        self.pcount_fails = 0
    
    
    # crash
    def crash_loop(self):
        if not self.crash_alive:
            self.crash_fails += 1
            self.console('server might have crashed! check %d of %d' % (self.crash_fails, self.crash_fail_limit))
            if self.crash_fails == self.crash_fail_limit:
                self.console('server has crashed, restarting...')
                self.dispatch(ServerStop(reason='crashed', respawn=True))
        
        self.register(self.handle_crash_ok, LineConsumer, level='INFO', pattern='Unknown command.*')
    
    def handle_crash_ok(self, event):
        self.crash_fails = 0
        self.crash_alive = True
    
    # out of memory
    def handle_oom(self, event):
        self.console('server out of memory, restarting...')
        self.dispatch(ServerStop(reason='out of memory', respawn=True))
    
    # ping
    def ping_loop(self):
        
    def handle_ping(self, event):
        

        
        self.crash_alive = False
        self.register(Consumer(self.crash_ok, 'INFO', 'Unknown command.*'))
        self.send('')  # Blank command to trigger 'Unknown command'
