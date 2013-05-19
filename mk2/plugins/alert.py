import os
import random

from mk2.plugins import Plugin


class Alert(Plugin):
    interval = 200
    command = "say {message}"
    path = "alerts.txt"
    
    messages = []
    
    def server_started(self, event):
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
