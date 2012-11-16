import os
import re

from plugins import Plugin, Command

class SU(Plugin):
    command  = "sudo -su {user} -- {command}"
    
    def setup(self):
        self.register(Command(self.su, "su", "run a command from your username, e.g. ~su ban Notch"))
    
    def su(self, user, line):
        self.send(self.command.format(user=user, command=line))
            
ref = SU
