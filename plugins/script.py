from plugins import Plugin, ShutdownTask, Interest, register

from collections import namedtuple
from subprocess import Popen
from time import localtime
import os.path
import re


class ScriptEntry(object):
    time_bounds = [(0, 59), (0, 23), (1, 31), (1, 12), (1, 7)]
    Range = namedtuple('Range', ('min', 'max', 'skip'))
    
    event = None
    ranges = None
    
    def __init__(self, line):
        self.line = line.strip()
        self.parse()
    
    def parse(self):
        if (self.line.startswith('@')):
            self.event, self.command = re.match(r'^@(\S+) (.+)$', self.line).groups()
        else:
            bits = re.split(r'\s+', self.line, 5)
            timespec, self.command = bits[:5], bits[5]
            self.ranges = map(self.parse_time, zip(timespec, self.time_bounds))
        print self.event or self.ranges
    
    def parse_time(self, (thing, bounds)):
        n, top, skip = re.match(r'^(\d{1,2}|\*)(?:-(\d{1,2}))?(?:/(\d{1,2}))?$', thing).groups()
        
        if n == '*':
            if top:
                raise Exception()
            return self.Range(bounds[0], bounds[1], int(skip or 1))
        else:
            return self.Range(int(n), int(top or n), int(skip or 1))
    
    def match_range(self, (test_range, value)):
        return value in range(test_range.min, test_range.max + 1, test_range.skip)
    
    def match(self, time=None, event=None):
        if self.event or event:
            return self.event == event
        time = time or localtime()
        # m h dom mon dow
        t = [time.tm_min, time.tm_hour, time.tm_mday, time.tm_mon, time.tm_wday + 1]
        return all(map(self.match_range, zip(self.ranges, t)))


class Script(Plugin):
    path = 'scripts.txt'
    shell = '/bin/sh'
    user = 'script'
    scripts = []
    
    def setup(self):
        try:
            if os.path.exists(self.path):
                self.init_scripts(self.path)
        except Exception:
            self.console('{}: invalid scripts file', kind='error')
        
        self.event('startup')
        self.repeating_task(self.event, 60)
    
    def shell_execute(self, cmd):
        Popen([self.shell, '-c', cmd])
    
    def execute(self, cmd):
        if cmd.startswith('~~'):
            self.shell_execute(cmd[2:])
        elif cmd.startswith('~'):
            self.parent.handle_plugin(self.user, cmd[1:])
        elif cmd.startswith('/'):
            self.parent.handle_command(self.user, cmd[1:])
        else:
            self.shell_execute(cmd)
    
    @register(ShutdownTask)
    def on_shutdown(self, reason):
        self.event('shutdown')
    
    @register(Interest, 'INFO', r'[A-Za-z0-9_]{1,16}: Save complete\.')
    def on_save(self, match):
        self.event('post-save')
    
    def init_scripts(self, path):
        with open(path, 'r') as f:
            self.scripts = map(ScriptEntry, [l for l in f.readlines() if not l.strip().startswith('#')])
        
    def event(self, name=None):
        for thing in self.scripts:
            if thing.match(event=name):
                self.execute(thing.command)
