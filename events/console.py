from events import Event, get_timestamp

prompts = {
    'server': '|',
    'user':   '>',
    'mark2':  '#'}

class Console(Event):
    requires = ['line']
    
    kind = None
    time = None
    user = ''
    source = 'mark2'
    
    def setup(self):
        self.time = get_timestamp(self.time)
        
        user = self.user.rjust(w) if len(self.user) < w else self.user[-w:]
        self._repr = "{user} {prompt} {time} {text}".format(user=user, prompt=self.prompt, time=self.time, line=self.line)
    
    def __repr__(self):
        return self._repr
