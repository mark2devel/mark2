from . import Event


class Hook(Event):
    name       = Event.Arg()
    is_command = Event.Arg()
    args       = Event.Arg()
    line       = Event.Arg()
    
    def setup(self):
        if not self.name:
            if self.line:
                t = self.line.split(" ", 1)
                
                self.name = t[0][1:]
                self.is_command = True
                if len(t) == 2:
                    self.args = t[1]
    
    def prefilter(self, name, public=False, doc=None):
        if name != self.name:
            return False
        
        if self.is_command and not public:
            return False
        
        return True
    
