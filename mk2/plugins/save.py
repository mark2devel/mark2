from mk2.plugins import Plugin
from mk2.events import Hook


class Save(Plugin):
    warn_message     = Plugin.Property(default="WARNING: saving map in {delay}.")
    message          = Plugin.Property(default="MAP IS SAVING.")
    warn_command     = Plugin.Property(default="say %s")
    save_command     = Plugin.Property(default="save-all")
    save_off_command = Plugin.Property(default="save-off")
    save_on_command  = Plugin.Property(default="save-on")
    save_allowed     = True
    
    def setup(self):
        self.register(self.save, Hook, public=True, name='save', doc='save the map')
        self.register(self.save_off, Hook, public=True, name='save-plugin-off', doc='Disable save plugin.')
        self.register(self.save_on, Hook, public=True, name='save-plugin-on', doc='Enable save plugin.')
    
    def warn(self, delay):
        self.send_format(self.warn_command % self.warn_message, delay=delay)
    
    def save(self, event):
        if (self.save_allowed):
            action = self.save_real
            if event.args:
                warn_length, action = self.action_chain(event.args, self.warn, action)
            action()
        event.handled = True

    def save_real(self):
        if self.message:
            self.send(self.warn_command % self.message)
        self.send(self.save_command)

    def save_off(self, event):
        self.save_allowed = False
        self.send(self.save_off_command)
        event.handled = True

    def save_on(self, event):
        self.save_allowed = True
        self.send(self.save_on_command)
        event.handled = True
    
