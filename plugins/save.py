from plugins import Plugin
from events import Hook, ServerSave


class Save(Plugin):
    warn_message = "WARNING: saving map in {delay}."
    message      = "MAP IS SAVING."
    
    def setup(self):
        self.register(self.save, Hook, public=True, name='save', doc='save the map')
        self.register(self.save_real, ServerSave)
    
    def warn(self, delay):
        self.send("say %s" % self.warn_message.format(delay=delay), parseColors=True)
    
    def save(self, event):
        action = self.save_real
        if event.args:
            warn_length, action = self.action_chain(event.args, self.warn, action)
        action()
        event.handled = True

    def save_real(self):
        self.send('say %s' % self.message, parseColors=True)
        self.send('save-all')
    
