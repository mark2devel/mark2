from events import Event

class Line(Event):
    def setup(self):
        self.regex = re.compile('^(?:\d{4}-\d{2}-\d{2} )?\d{2}:\d{2}:\d{2} \[%s\] %s$' % (self.level, self.pattern))
    
    def consider(r_args):
        return self.regex.match(r_args['line'])
