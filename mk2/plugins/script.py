import re
import os.path
import pwd
from time import localtime
from collections import namedtuple

from twisted.internet import protocol, reactor, defer

from mk2.plugins import Plugin
from mk2 import events

time_bounds = [(0, 59), (0, 23), (1, 31), (1, 12), (1, 7)]


class ScriptEntry(object):
    event = None
    ranges = None
    
    def __init__(self, plugin, line):
        self.plugin = plugin
        
        line = line.strip()
        if line.startswith('@'):
            self.type = "event"
            event_name, command = re.match(r'^@([^\s]+)\s+(.+)$', line).groups()
            event = events.get_by_name(event_name)
            if not event:
                raise ValueError("unknown event: %s" % event_name)
            self.plugin.register(lambda e: self.execute(command), event)
        else:
            self.type = "time"
            bits = re.split(r'\s+', line, 5)
            time_spec, self.command = bits[:5], bits[5]
            self.ranges = self.parse_time(time_spec)
    
    def parse_time(self, time_spec):
        Range = namedtuple('Range', ('min', 'max', 'skip'))
        ranges = []
        for spec_i, bound_i in zip(time_spec, time_bounds):
            n, top, skip = re.match(r'^(\d{1,2}|\*)(?:-(\d{1,2}))?(?:/(\d{1,2}))?$', spec_i).groups()
            if n == '*':
                if top:
                    raise ValueError("can't use * in a range expression")
                ranges.append(Range(bound_i[0], bound_i[1], int(skip or 1)))
            else:
                ranges.append(Range(int(n), int(top or n), int(skip or 1)))
        return ranges
 
    def execute(self, cmd):
        execute = defer.succeed(None)

        def execute_next(fn, *a, **kw):
            execute.addCallback(lambda r: fn(*a, **kw))
            execute.addErrback(lambda f: True)

        if cmd.startswith('$'):
            cmd = cmd[1:]
            d = defer.Deferred()

            p = protocol.ProcessProtocol()
            p.outReceived = lambda d: [execute_next(self.execute_reduced, l, cmd) for l in d.split("\n")]
            p.processEnded = lambda r: d.callback(None)

            reactor.spawnProcess(p, self.plugin.shell, [self.plugin.shell, '-c', cmd])

            d.addCallback(lambda r: execute)
            return d
        else:
            return self.execute_reduced(cmd)
    
    @defer.inlineCallbacks
    def execute_reduced(self, cmd, source='script'):
        if cmd.startswith('~'):
            handled = yield self.plugin.dispatch(events.Hook(line=cmd))
            if not handled:
                self.plugin.console("unknown command in script: %s" % cmd)
        elif cmd.startswith('/'):
            self.plugin.send(cmd[1:])
        elif cmd.startswith('#'):
            self.plugin.console("#{0}".format(cmd[1:]), user=source, source="user")
        elif cmd:
            self.plugin.console("couldn't understand script input: %s" % cmd)

    def step(self):
        if self.type != 'time':
            return
        time = localtime()
        time = [time.tm_min, time.tm_hour, time.tm_mday, time.tm_mon, time.tm_wday + 1]
        
        for r, t in zip(self.ranges, time):
            if not t in range(r.min, r.max + 1, r.skip):
                return
        
        self.execute(self.command)


class Script(Plugin):
    path = Plugin.Property(default='scripts.txt')
    shell = Plugin.Property(default='/bin/sh')
    
    def setup(self):
        self.scripts = []
        if not os.path.isfile(self.path):
            return
        
        with open(self.path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or line == '':
                    continue
                try:
                    self.scripts.append(ScriptEntry(self, line))
                except Exception as e:
                    self.console('invalid script line: %s' % line, kind='error')
                    self.console(str(e))
        
        for script in self.scripts:
            if script.type == 'time':
                self.delayed_task(lambda a: self.repeating_task(self.step, 60, now=True),
                                  max(0, 60 - localtime().tm_sec) % 60 + 1)
                break

    def step(self, event):
        for script in self.scripts:
            script.step()

    def server_stopping(self, event):
        pass  # don't cancel tasks
