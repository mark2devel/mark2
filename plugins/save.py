from plugins import Plugin, Command

class Save(Plugin):
    interval = 625
    warn_delay = 60
    def setup (self):
        self.repeating_task(self.warn, self.interval-self.warn_delay)
        self.register(Command(self.warn, 'save-warn'))
        self.register(Command(self.save, 'save'))
    
    def warn(self, *a):
        """warn the playerbase of an impending map save and schedule it"""
        self.send('say SAVING IN %d SECONDS.' % self.warn_delay)
        self.delayed_task(self.save, self.warn_delay)
    
    def save(self, *a):
        """save the map"""
        self.send('say MAP IS SAVING.')
        self.send('save-all')

ref = Save
