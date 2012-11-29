from plugins import Plugin, Command, register


class Save(Plugin):
    warn_delay = 60
    
    def setup(self):
        self.register(self.warn, Hook, public=True, name='save-warn')
        self.register(self.save, Hook, public=True, name='save')
    
    def warn(self, event):
        """warn the playerbase of an impending map save and schedule it"""
        self.send('say SAVING IN %d SECONDS.' % self.warn_delay)
        self.delayed_task(self.save, self.warn_delay)
    
    def save(self, event):
        """save the map"""
        self.send('say MAP IS SAVING.')
        self.send('save-all')
