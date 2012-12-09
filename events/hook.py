from events import Event, ACCEPTED

class Hook(Event):
    contains = ('name', 'is_command', 'args')
    requires = tuple()
    requires_predicate = ('name',)
    name = None
    is_command = False
    args = None
    line = None
    
    def setup(self):
        if not self.name:
            if self.line:
                t = self.line.split(" ", 1)
                
                self.name = t[0][1:]
                self.is_command = True
                if len(t) == 2:
                    self.args = t[1]
    
    def consider(self, r_args):
        d = {
            'public': False,
            'doc':    None}
        
        d.update(r_args)
        
        if r_args['name'] != self.name:
            return 0
        
        if self.is_command and not r_args['public']:
            return 0
        
        return ACCEPTED
    
