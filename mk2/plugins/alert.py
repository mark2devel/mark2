import os
import random

from mk2.plugins import Plugin


class Alert(Plugin):
    interval = Plugin.Property(default=200)
    command  = Plugin.Property(default="say {message}")
    path     = Plugin.Property(default="alerts.txt")
    
    messages = []
    
    def setup(self):
        if self.path and os.path.exists(self.path):
            f = open(self.path, 'r')
            for l in f:
                l = l.strip()
                if l:
                    self.messages.append(l)
            f.close()
            
            if self.messages:
                self.repeating_task(self.repeater, self.interval)

    def repeater(self, event):
        self.send_format(self.command, parseColors=True, message=random.choice(self.messages))
