import re
import os.path
import pwd
from time import localtime
from collections import namedtuple

from twisted.internet import protocol, reactor

from plugins import Plugin
import events

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
        if cmd.startswith('$'):
            p = protocol.ProcessProtocol()
            p.outReceived = lambda d: [self.execute_reduced(l) for l in d.split("\n")]
            reactor.spawnProcess(p, self.plugin.shell, [self.plugin.shell, '-c', cmd[1:]], uid=self.plugin.uid)
        else:
            self.execute_reduced(cmd)
    
    def execute_reduced(self, cmd):
        if cmd.startswith('~'):
            r = self.plugin.dispatch(events.Hook(line=cmd))
            if not r & events.ACCEPTED:
                self.plugin.console("unknown command: %s" % cmd)
        elif cmd.startswith('/'):
            self.plugin.send(cmd[1:])
        else:
            self.plugin.console("couldn't understand script input: %s" % cmd)

    def step(self):
        if self.type != 'time': return
        time = localtime()
        time = [time.tm_min, time.tm_hour, time.tm_mday, time.tm_mon, time.tm_wday + 1]
        
        for r, t in zip(self.ranges, time):
            if not t in range(r.min, r.max + 1, r.skip):
                return
        
        self.execute(self.command)


class Script(Plugin):
    path = 'scripts.txt'
    shell = '/bin/sh'
    user = ''
    
    def setup(self):
        self.uid = None
        if self.user != '':
            try:
                self.uid = pwd.getpwnam(self.user).pw_uid
            except KeyError:
                self.console("warning: couldn't get uid of script user '%s'" % self.user)
        
        self.scripts = []
        if not os.path.isfile(self.path):
            self.console("file doesn't exist: %s" % self.path, kind='error')
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
                self.repeating_task(self.step, 60)
                break
    
    def step(self, event):
        for script in self.scripts:
            script.step()

    def server_stopping(self, event):
        pass #don't cancel tasks