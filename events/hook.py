from events import Event, ACCEPTED

class Hook(Event):
    contains = ('name', 'is_command', 'args')
    requires = ('name',)
    requires_predicate = ('name',)
    is_command = False
    args = None
    
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
    
