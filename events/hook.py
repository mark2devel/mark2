from events import Event

class Hook(Event):
    requires = ['name']
    public = False #Public commands are callable by prefixing their name on the command line
    doc = None
    
    def consider(self, r_args):
        return r_args['name'] == self.name
    
    def __repr__(self):
        o = "  ~%s" % self.command
        if self.doc:
            o += ": %s" % self.doc
        return o
