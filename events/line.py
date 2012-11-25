import re

from events import Event

class Line(Event):
    requires = ['line']
    
    def consider(self, r_args):
        return self.extra(r_args) != {}
    
    def extra(self, r_args):
        return {'match': re.match('^(?:\d{4}-\d{2}-\d{2} )?\d{2}:\d{2}:\d{2} \[%s\] %s$' % (r_args['level'], r_args['pattern']), self.line)}
