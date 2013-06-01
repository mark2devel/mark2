from mk2.plugins import Plugin
from mk2.events import UserInput


class Su(Plugin):
    command = Plugin.Property(default="sudo -su {user} -- {command}")
    mode = Plugin.Property(default="include")
    proc = Plugin.Property(default="ban;unban")
    
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
