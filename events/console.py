from events import Event, get_timestamp

class Console(Event):
    contains = ('line', 'time', 'user', 'source', 'kind', 'data')
    requires = ('line',)
    
    
    kind = None
    time = None
    user = ''
    source = 'mark2'
    data = None
    
    def setup(self):
        if not self.time:
            self.time = get_timestamp(self.time)
        if not self.data:
            self.data = self.line
        
    def __repr__(self):
        s = "%s %s " % (self.time, {'server': '|', 'mark2': '#', 'user': '>'}.get(self.source, '?'))
        if self.source == 'server' and self.level != 'INFO':
            s += "[%s] " % self.level
        elif self.source == 'user':
            s += "(%s) " % self.user
        
        s += "%s" % self.data
        return s
