from mk2.plugins import Plugin
from mk2.events import Hook


class Save(Plugin):
    warn_message = Plugin.Property(default="WARNING: saving map in {delay}.")
    message      = Plugin.Property(default="MAP IS SAVING.")
    warn_command = Plugin.Property(default="say %s")
    save_command = Plugin.Property(default="save-all")
    
    def setup(self):
        self.register(self.save, Hook, public=True, name='save', doc='save the map')
    
    def warn(self, delay):
        self.send_format(self.warn_command % self.warn_message, delay=delay)
    
    def save(self, event):
        action = self.save_real
        if event.args:
            warn_length, action = self.action_chain(event.args, self.warn, action)
        action()
        event.handled = True

    def save_real(self):
        if self.message:
            self.send(self.warn_command % self.message)
        self.send(self.save_command)
    
