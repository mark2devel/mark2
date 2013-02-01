from events import Event, get_timestamp
from shared import console_repr


class Console(Event):
    contains = ('line', 'time', 'user', 'source', 'kind', 'data', 'level')
    requires = ('line',)
    
    kind = None
    time = None
    user = ''
    source = 'mark2'
    data = None
    level = None
    
    def setup(self):
        if not self.time:
            self.time = get_timestamp(self.time)
        if not self.data:
            self.data = self.line
        
    def value(self):
        return console_repr(self)
