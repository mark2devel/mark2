import os
import re

def load(*files):
    o = None
    for f in files:
        if os.path.isfile(f):
            o = Properties(f, o)
    return o
        
class Properties(dict):
    def __init__(self, path, parent=None):
        dict.__init__(self)

        if parent:
            self.update(parent)
            self.types = dict(parent.types)
        else:
            self.types = {}
        
        decoder = {
            'int': int,
            'bool': lambda a: a == 'true',
            'string': lambda a: a.replace('\:', ':').replace('\=', '='),
            'none': lambda a: None
        }
        ty = None
        
        f = open(path)
        for l in f:
            #Comment
            if l.startswith('#'):
                continue
            
            #K,V pair
            m = re.match('^([^=]+)=(.*)$', l.strip())
            if m:
                k, v = m.groups()
                k = k.replace('-', '_')
                
                if re.match('^\-?\d+$', v):
                    ty = 'int'
                elif v in ('true', 'false'):
                    ty = 'bool'
                elif v != '':
                    ty = 'string'
                elif k in self.types:
                    ty = self.types[k]
                else:
                    ty = 'string'
                
                self.types[k] = ty
                self[k] = decoder[ty](v)

    def get_plugins(self):
        plugins = {}
        enabled = []
        for k, v in self.iteritems():
            m = re.match('^plugin\.(.+)\.(.+)$', k)
            if m:
                plugin, k2 = m.groups()
                
                if plugin not in plugins:
                    plugins[plugin] = {}
                
                if k2 == 'enabled':
                    if v:
                        enabled.append(plugin)
                else:
                    plugins[plugin][k2] = v

        for n in sorted(enabled):
            yield n, plugins[n]

    def get_jvm_options(self):
        options = []
        for k, v in self.iteritems():
            m = re.match('^java\.cli\.([^\.]+)\.(.+)$', k)
            if m:
                a, b = m.groups()
                if a == 'D':
                    options.append('-D%s=%s' % (b, v))
                elif a == 'X':
                    options.append('-X%s%s' % (b, v))
                elif a == 'XX':
                    if v in (True, False):
                        options.append('-XX:%s%s' % ('+' if v else '-', b))
                    else:
                        options.append('-XX:%s=%s' % (b, v))
                else:
                    print "Unknown JVM option type: %s" % a
        return options
    
    def get_format_options(self):
        options = {}
        for k, v in self.iteritems():
            m = re.match('^mark2\.format\.(.*)$', k)
            if m:
                options[m.group(1)] = v
        return options
