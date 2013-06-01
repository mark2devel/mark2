import time
import glob
import os
from twisted.internet import protocol, reactor, defer

from mk2.plugins import Plugin
from mk2.events import Hook, ServerOutput, ServerStopped, EventPriority
import shlex


class Backup(Plugin):
    path = Plugin.Property(default="backups/{timestamp}.tar.gz")
    mode = Plugin.Property(default="include")
    spec = Plugin.Property(default="world*")
    tar_flags = Plugin.Property(default='-hpczf')
    flush_wait = Plugin.Property(default=5)

    backup_stage = 0
    autosave_enabled = True
    proto = None
    done_backup = None
    
    def setup(self):
        self.register(self.backup, Hook, public=True, name='backup', doc='backup the server to a .tar.gz')
        self.register(self.autosave_changed, ServerOutput, pattern="(?P<username>[A-Za-z0-9_]{1,16}): (?P<action>Enabled|Disabled) level saving\.\.")
        self.register(self.autosave_changed, ServerOutput, pattern="Turned (?P<action>on|off) world auto-saving")
        self.register(self.server_stopped, ServerStopped, priority=EventPriority.HIGHEST)

    def server_started(self, event):
        self.autosave_enabled = True

    @EventPriority.HIGH
    @defer.inlineCallbacks
    def server_stopping(self, event):
        if self.backup_stage > 0:
            self.console("backup: delaying server stop until backup operation completes.")
            yield self.done_backup
            self.stop_tasks()
        self.autosave_enabled = False

    def server_stopped(self, event):
        self.autosave_enabled = False

    def save_state(self):
        if self.proto:
            self.console("stopping in-progress backup!")
            self.proto.transport.signalProcess('KILL')
        if self.done_backup:
            self.done_backup.callback(None)

        return self.autosave_enabled

    def load_state(self, state):
        self.autosave_enabled = state

    def autosave_changed(self, event):
        self.autosave_enabled = event.match.groupdict()['action'].lower() in ('on', 'enabled')
        if self.backup_stage == 1 and not self.autosave_enabled:
            self.backup_stage = 2
            self.delayed_task(self.do_backup, self.flush_wait)
        elif self.backup_stage == 2:
            self.console("warning: autosave changed while backup was in progress!")

    def backup(self, event):
        if self.backup_stage > 0:
            self.console("backup already in progress!")
            return

        self.done_backup = defer.Deferred()

        self.console("map backup starting...")
        self.autosave_enabled_prev = self.autosave_enabled
        if self.autosave_enabled:
            self.backup_stage = 1
            self.send('save-off')
        else:
            self.backup_stage = 2
            self.do_backup()

        return self.done_backup

    def do_backup(self, *a):
        timestamp = time.strftime("%Y-%m-%d-%H:%M:%S", time.gmtime())
        path = self.path.format(timestamp=timestamp, name=self.parent.server_name)
        if not os.path.exists(os.path.dirname(path)):
            try:
                os.makedirs(os.path.dirname(path))
            except IOError:
                self.console("Warning: {0} does't exist and I can't create it".format(os.path.dirname(path)),
                             kind='error')
                return

        if self.mode == "include":
            add = set()
            for e in self.spec.split(";"):
                add |= set(glob.glob(e))
        elif self.mode == "exclude":
            add = set(glob.glob('*'))
            for e in self.spec.split(";"):
                add -= set(glob.glob(e))

        cmd = ['tar']
        cmd.extend(shlex.split(self.tar_flags))
        cmd.append(path)
        cmd.extend(add)

        def p_ended(path):
            self.console("map backup saved to %s" % path)
            if self.autosave_enabled_prev:
                self.send('save-on')
            self.backup_stage = 0
            self.proto = None
            if self.done_backup:
                d = self.done_backup
                self.done_backup = None
                d.callback(None)

        self.proto = protocol.ProcessProtocol()
        self.proto.processEnded = lambda reason: p_ended(path)
        self.proto.childDataReceived = lambda fd, d: self.console(d.strip())
        reactor.spawnProcess(self.proto, "/bin/tar", cmd)

