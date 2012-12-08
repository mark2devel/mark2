from plugins import Plugin
from events import Hook, ServerSave


class Save(Plugin):
    repeat = True
    repeat_interval      = "10m"
    repeat_warn_interval = "1m"
    
    warn_message = "WARNING: saving map in {delay}."
    message      = "MAP IS SAVING."
    
    def setup(self):
        self.register(self.save, Hook, public=True, name='save', doc='save the map')
        self.register(self.save_real, ServerSave)
    
    def server_started(self, event):
        if self.repeat:
            length, chain = self.action_chain(self.repeat_warn_interval, self.warn, self.save_real)
            interval = self.parse_time(self.repeat_interval)[1]
            self.repeating_task(chain, interval)
    
    def warn(self, delay):
        self.send("say %s" % self.warn_message.format(delay=delay))
    
    def save(self, event):
        action = self.save_real
        if event.args:
            warn_length, action = self.action_chain(event.args, self.warn, action)
        action()
        event.handled = True

    def save_real(self):
        self.send('say %s' % self.message)
        self.send('save-all')
    
