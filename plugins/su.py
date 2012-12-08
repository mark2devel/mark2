from plugins import Plugin
from events import UserInput
import re

class Su(Plugin):
    command = "sudo -su {user} -- {command}"
    mode = "include"
    proc = "ban;unban"
    
    def setup(self):
        self.register(self.uinput, UserInput)
    
    def uinput(self, event):
        handled = False
        for p in self.proc.split(";"):
            if event.line.startswith(p):
                handled = True
                break
        
        if (self.mode == 'exclude') ^ handled:
            event.line = self.command.format(user=event.user, command=event.line)
