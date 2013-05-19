from . import Event, get_timestamp
from ..shared import console_repr


class Console(Event):
    contains = ('line', 'time', 'user', 'source', 'kind', 'data', 'level')
    requires = ('line',)

    line  = Event.Arg(required=True)
    kind  = Event.Arg()
    time  = Event.Arg()
    user  = Event.Arg(default='')
    source = Event.Arg(default='mark2')
    data  = Event.Arg()
    level = Event.Arg()
    
    def setup(self):
        if not self.time:
            self.time = get_timestamp(self.time)
        if not self.data:
            self.data = self.line
        
    def value(self):
        return console_repr(self)
