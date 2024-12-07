from mk2.plugins import Plugin
from mk2.events import ServerOutput, StatPlayerCount, ServerStop, ServerEvent, Event


class Check:
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
            timeout = "{} minutes".format(self.timeout)
            self.console("{} -- restarting.".format(self.message.format(timeout=timeout)))
            self.dispatch(ServerEvent(cause="server/error/" + self.event[0],
                                      data="REBOOTING SERVER: " + self.event[1].format(timeout=timeout),
                                      priority=1))
            self.dispatch(ServerStop(reason=self.stop_reason, respawn=ServerStop.RESTART))
        elif self.warn and self.time == self.warn:
            if self.timeout:
                self.console("{} -- auto restart in {} minutes".format(self.warning, self.timeout - self.time))
            else:
                self.console(self.warning)
            time = "{} minutes".format(self.warn)
            self.dispatch(ServerEvent(cause="server/warning/" + self.event[0],
                                      data="WARNING: " + self.event[1].format(timeout=time),
                                      priority=1))
        else:
            if self.timeout:
                self.console("{} -- auto restart in {} minutes".format(self.warning, self.timeout - self.time))
            else:
                self.console(self.warning)

    def reset(self):
        self.alive = True
        self.time = 0


class Monitor(Plugin):
    crash_enabled  = Plugin.Property(default=True)
    crash_timeout  = Plugin.Property(default=3)
    crash_warn     = Plugin.Property(default=0)
    crash_unknown_cmd_message    = Plugin.Property(default="Unknown.*command.*")
    crash_check_command          = Plugin.Property(default="")
    crash_check_command_message  = Plugin.Property(default="")

    oom_enabled          = Plugin.Property(default=True)
    crash_report_enabled = Plugin.Property(default=True)
    jvm_crash_enabled    = Plugin.Property(default=True)

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
            self.register(self.handle_oom, ServerOutput, level='SEVERE', pattern=r'java\.lang\.OutOfMemoryError.*')

        if self.crash_report_enabled:
            self.register(self.handle_unknown_crash, ServerOutput, level='ERROR', pattern='This crash report has been saved to.*')

        if self.jvm_crash_enabled:
            self.register(self.handle_jvm_crash, ServerOutput, level='RAW', pattern='.*A fatal error has been detected by the Java Runtime Environment:.*')

        if self.crash_enabled:
            do_step = True
            self.checks['crash'] =  Check(self, name="crash",
                                          timeout=self.crash_timeout,
                                          warn=self.crash_warn,
                                          message="server might have crashed: not accepting accepting console commands or crash-unknown-cmd-message is not set",
                                          warning="server might have crashed",
                                          event=("hang", "server didn't respond for {timeout}"),
                                          stop_reason="crashed")

        if self.ping_enabled:
            self.register(self.handle_ping, StatPlayerCount)
            do_step = True
            self.checks['ping'] =   Check(self, name="ping",
                                          timeout=self.ping_timeout,
                                          warn=self.ping_warn,
                                          message="server might have crashed: not accepting connections or wrong port is being pinged.",
                                          warning="server might have stopped accepting connections",
                                          event=("ping", "server didn't respond for {timeout}"),
                                          stop_reason="not accepting connections")

        if self.pcount_enabled:
            self.register(self.handle_pcount, StatPlayerCount)
            do_step = True
            self.checks['pcount'] = Check(self, name="pcount",
                                          timeout=self.pcount_timeout,
                                          warn=self.pcount_warn,
                                          message="server might have crashed: has had 0 players for {timeout}",
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
            self.register(self.handle_crash_ok, ServerOutput,
                          pattern=self.crash_check_command_message,
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
        self.dispatch(ServerStop(reason='out of memory', respawn=ServerStop.RESTART))

    # unknown crash
    def handle_unknown_crash(self, event):
        self.console('server crashed for unknown reason, restarting...')
        self.dispatch(ServerEvent(cause='server/error/unknown',
                                  data="server crashed for unknown reason",
                                  priority=1))
        self.dispatch(ServerStop(reason='unknown reason', respawn=ServerStop.RESTART))

    # jvm crash
    def handle_jvm_crash(self, event):
        self.console('server jvm crashed, restarting...')
        self.dispatch(ServerEvent(cause='server/error/jvm',
                                  data="server jvm crashed",
                                  priority=1))
        self.dispatch(ServerStop(reason='jvm crash', respawn=ServerStop.RESTART))

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
