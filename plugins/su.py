from plugins import Plugin, Command


class Su(Plugin):
    command = "sudo -su {user} -- {command}"
    
    def setup(self):
        # register ~raw if commands are modified in any way,
        # register ~su if commands do not get 'sudo ' at the beginning
        if self.parent.expand_command('', '') != '':
            self.register(Command(self.raw, "raw", "send a command unmodified to the server"))
        if not self.parent.expand_command('', '').lower().startswith('sudo '):
            self.register(Command(self.su, "su", "run a command from your username, e.g. ~su ban Notch"))
    
    def su(self, user, line):
        self.send(self.command.format(user=user, command=line))
    
    def raw(self, user, line):
        self.send(line)
