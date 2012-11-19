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

    pcount_enabled = False
    pcount_interval = 60
    pcount_fail_limit = 10
    
    def setup(self):
        self.reset_counts()
        if self.crash_enabled:
            self.repeating_task(self.crash_loop, self.crash_interval)
        if self.oom_enabled:
            self.register(Interest(self.out_of_memory, 'SEVERE', 'java\.lang\.OutOfMemoryError.*'))
        if self.ping_enabled:
            pass  # TODO
        if self.pcount_enabled:
            pass  # TODO
    
    @register(ShutdownTask)
    def reset_counts(self, *a):
        self.crash_alive  = True
        self.crash_fails  = 0
        self.ping_alive   = True
        self.ping_fails   = 0
        self.pcount_alive = True
        self.pcount_fails = 0
        
    def out_of_memory(self, match):
        self.console('server out of memory, restarting...')
        self.parent.failure = 'out-of-memory'
        self.plugins['shutdown'].hard_restart()
    
    def crash_ok(self, match):
        self.crash_fails = 0
        self.crash_alive = True
    
    def crash_loop(self):
        if not self.crash_alive:
            self.crash_fails += 1
            self.console('server might have crashed! check %d of %d' % (self.crash_fails, self.crash_fail_limit))
            if self.crash_fails == self.crash_fail_limit:
                self.console('server has crashed, restarting...')
                self.parent.failure = 'crash'
                self.plugins['shutdown'].hard_restart()
        
        self.crash_alive = False
        self.register(Consumer(self.crash_ok, 'INFO', 'Unknown command.*'))
        self.send('')  # Blank command to trigger 'Unknown command'
