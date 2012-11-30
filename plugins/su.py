from plugins import Plugin
from events import UserInput
import re

modes = ('raw', 'su')

class Su(Plugin):
    command = "sudo -su {user} -- {command}"
    default = "raw"
    exceptions = ""
    
    def setup(self):
        self.exceptions = re.split("\s*[\;\,]\s*", self.exceptions)
        self.register(self.uinput, UserInput)
    
    def uinput(self, event):
        is_raw = (self.default == modes[1]) ^ (event.line in self.exceptions)
        if is_raw:
            self.send(event.line)
        else:
            self.send(self.command.format(user=event.user, command=event.line))
        
        event.handled   = True
        event.cancelled = True
