from mk2.plugins import Plugin
from mk2.events import ServerOutput, StatPlayerCount, ServerStop, ServerEvent, Event


class Check(object):
    alive = True
    timeout = 0
    time = 0
    warn = 0

    def __init__(self, parent, **kw):
        self.dispatch = parent.dispatch
        self.console = parent.console
        for k, v in kw.items():
            setattr(self, k, v)

    def check(self):
        if self.alive:
            self.alive = False
            return True
        return False

    def step(self):
        if self.check():
            return

        self.time += 1
        if self.timeout and self.time == self.timeout:
            timeout = "{0} minutes".format(self.timeout)
            self.console("{0} -- restarting.".format(self.message.format(timeout=timeout)))
            self.dispatch(ServerEvent(cause="server/error/" + self.event[0],
                                      data="REBOOTING SERVER: " + self.event[1].format(timeout=timeout),
                                      priority=1))
            self.dispatch(ServerStop(reason=self.stop_reason, respawn=True))
        elif self.warn and self.time == self.warn:
            if self.timeout:
                self.console("{0} -- auto restart in {1} minutes".format(self.warning, self.timeout - self.time))
            else:
                self.console(self.warning)
            time = "{0} minutes".format(self.warn)
            self.dispatch(ServerEvent(cause="server/warning/" + self.event[0],
                                      data="WARNING: " + self.event[1].format(timeout=time),
                                      priority=1))
        else:
            if self.timeout:
                self.console("{0} -- auto restart in {1} minutes".format(self.warning, self.timeout - self.time))
            else:
                self.console(self.warning)

    def reset(self):
        self.alive = True
        self.time = 0


class Monitor(Plugin):
    crash_enabled  = Plugin.Property(default=True)
    crash_timeout  = Plugin.Property(default=3)
    crash_warn     = Plugin.Property(default=0)
    crash_unknown_cmd_message    = Plugin.Property(default="Unknown command.*")
    crash_check_command    = Plugin.Property(default="")

    oom_enabled    = Plugin.Property(default=True)

    ping_enabled   = Plugin.Property(default=True)
    ping_timeout   = Plugin.Property(default=3)
    ping_warn      = Plugin.Property(default=0)

    pcount_enabled = Plugin.Property(default=False)
    pcount_timeout = Plugin.Property(default=3)
    pcount_warn    = Plugin.Property(default=0)

    def setup(self):
        do_step = False
        self.checks = {}

        if self.oom_enabled:
            self.register(self.handle_oom, ServerOutput, level='SEVERE', pattern='java\.lang\.OutOfMemoryError.*')

        if self.crash_enabled:
            do_step = True
            self.checks['crash'] =  Check(self, name="crash",
                                          timeout=self.crash_timeout,
                                          warn=self.crash_warn,
                                          message="server has crashed",
                                          warning="server might have crashed",
                                          event=("hang", "server didn't respond for {timeout}"),
                                          stop_reason="crashed")

        if self.ping_enabled:
            self.register(self.handle_ping, StatPlayerCount)
            do_step = True
            self.checks['ping'] =   Check(self, name="ping",
                                          timeout=self.ping_timeout,
                                          warn=self.ping_warn,
                                          message="server is not accepting connections",
                                          warning="server might have stopped accepting connections",
                                          event=("ping", "server didn't respond for {timeout}"),
                                          stop_reason="not accepting connections")

        if self.pcount_enabled:
            self.register(self.handle_pcount, StatPlayerCount)
            do_step = True
            self.checks['pcount'] = Check(self, name="pcount",
                                          timeout=self.pcount_timeout,
                                          warn=self.pcount_warn,
                                          message="server has had 0 players for {timeout}, something is wrong",
                                          warning="server has 0 players, might be inaccessible",
                                          event=("player-count", "server had 0 players for {timeout}"),
                                          stop_reason="zero players")

        self.do_step = do_step

    def server_started(self, event):
        self.reset_counts()
        if self.do_step:
            self.repeating_task(self.step, 60)

    def load_state(self, state):
        self.server_started(None)

    def step(self, *a):
        for c in self.checks.values():
            c.step()

        if self.crash_enabled:
            self.register(self.handle_crash_ok, ServerOutput,
                          pattern=self.crash_unknown_cmd_message,
                          track=False)
            self.send(self.crash_check_command)  # Blank command to trigger 'Unknown command'
    
    def reset_counts(self):
        for c in self.checks.values():
            c.reset()

    ### handlers
    
    # crash
    def handle_crash_ok(self, event):
        self.checks["crash"].reset()
        return Event.EAT | Event.UNREGISTER
    
    # out of memory
    def handle_oom(self, event):
        self.console('server out of memory, restarting...')
        self.dispatch(ServerEvent(cause='server/error/oom',
                                  data="server ran out of memory",
                                  priority=1))
        self.dispatch(ServerStop(reason='out of memory', respawn=True))

    # ping
    def handle_ping(self, event):
        if event.source == 'ping':
            self.checks["ping"].reset()
    
    # pcount
    def handle_pcount(self, event):
        if event.players_current > 0:
            self.checks["pcount"].reset()
        else:
            self.checks["pcount"].alive = False
