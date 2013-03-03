from plugins import Plugin
from events import ServerOutput, ServerOutputConsumer, StatPlayerCount, ServerStop
from events import ACCEPTED, FINISHED

class HangChecker(Plugin):
    crash_enabled = True
    crash_timeout = 3

    oom_enabled   = True

    ping_enabled  = True
    ping_timeout  = 3

    pcount_enabled = False
    pcount_timeout = 3

    def setup(self):
        do_step = False
        if self.crash_enabled:
            do_step = True

        if self.oom_enabled:
            self.register(self.handle_oom, ServerOutput, level='SEVERE', pattern='java\.lang\.OutOfMemoryError.*')

        if self.ping_enabled:
            self.register(self.handle_ping, StatPlayerCount)
            do_step = True

        if self.pcount_enabled:
            self.register(self.handle_pcount, StatPlayerCount)
            do_step = True

        self.do_step = do_step

    def server_started(self, event):
        self.reset_counts()
        if self.do_step:
            self.repeating_task(self.step, 60)

    def step(self, *a):
        if self.crash_enabled:
            if not self.crash_alive:
                self.crash_time -= 1
                if self.crash_time == 0:
                    self.console("server has crashed, restarting...")
                    self.dispatch(ServerStop(reason='crashed', respawn=True))
                else:
                    self.console("server might have crashed! will auto-reboot in %d minutes." % self.crash_time)

            self.crash_alive = False
            self.register(self.handle_crash_ok, ServerOutputConsumer, pattern='Unknown command.*', once=True, track=False)
            self.send('') # Blank command to trigger 'Unknown command'

        if self.ping_enabled:
            if not self.ping_alive:
                self.ping_time -= 1
                if self.ping_time == 0:
                    self.console("server has stopped accepting connections, restarting...")
                    self.dispatch(ServerStop(reason='not accepting connections', respawn=True))
                else:
                    self.console("server might have stopped accepting connections! will auto-reboot in %d minutes." % self.ping_time)

            self.ping_alive = False

        if self.pcount_enabled:
            if not self.pcount_alive:
                self.pcount_time -= 1
                if self.pcount_time == 0:
                    self.console("server has had 0 players for ages - something is awry. restarting...")
                    self.dispatch(ServerStop(reason='zero players', respawn=True))
                else:
                    self.console("server has 0 players on! might be down? will auto-reboot in %d minutes" % self.pcount_time)

    
    def reset_counts(self):
        self.crash_alive  = True
        self.crash_time   = self.crash_timeout
        self.ping_alive   = True
        self.ping_time    = self.ping_timeout
        self.pcount_alive = True
        self.pcount_time  = self.pcount_timeout

    ### handlers
    
    # crash
    def handle_crash_ok(self, event):
        self.crash_time = self.crash_timeout
        self.crash_alive = True
        return ACCEPTED | FINISHED
    
    # out of memory
    def handle_oom(self, event):
        self.console('server out of memory, restarting...')
        self.dispatch(ServerStop(reason='out of memory', respawn=True))

    # ping
    def handle_ping(self, event):
        if event.source=='ping':
            self.ping_time = self.ping_timeout
            self.ping_alive = True
    
    # pcount
    def handle_pcount(self, event):
        if event.players_count > 0:
            self.pcount_time = self.pcount_timeout
            self.pcount_alive = True
