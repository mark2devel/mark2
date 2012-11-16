import os
import random

from plugins import Plugin

class Alert(Plugin):
    interval = 200
    command  = "say {message}"
    path = "alerts.txt"
    
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

    def repeater(self):
        self.send(self.command.format(message=random.choice(self.messages)))

ref = Alert
