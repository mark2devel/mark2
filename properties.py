import re

class Properties(dict):
    def __init__(self, path, parent=None):
        if parent:
            self.update(parent)
            self.types = dict(parent.types)
        else:
            self.types = {}
        
        decoder = {
            'int': int,
            'bool': lambda a: a=='true',
            'string': lambda a: a.replace('\:', ':').replace('\=', '=').strip(),
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
                self[k]  = decoder[ty](v)

    def get_plugins(self):
        plugins = {}
        enabled = []
        for k, v in self.iteritems():
            m = re.match('^plugin\.(.+)\.(.+)$', k)
            if m:
                plugin, k2 = m.groups()
                k2 = k2.replace('-', '_')
                
                if plugin not in plugins:
                    plugins[plugin] = {}
                
                if k2 == 'enabled':
                    if v:
                        enabled.append(plugin)
                else:
                    plugins[plugin][k2] = v
        
        return [(plugin, plugins[plugin]) for plugin in enabled]

    def get_jvm_options(self):
        options = []
        for k, v in self.iteritems():
            m = re.match('^java\.cli\.([^\.]+)\.(.+)$', k)
            if m:
                a, b = m.groups()
                if a == 'D': 
                    options.append('-D%s=%s' % (b,v))
                elif a == 'X': 
                    options.append('-X%s%s' % (b,v))
                elif a == 'XX':
                    if v in (True, False):
                        options.append('-XX:%s%s' % ('+' if v else '-', b))
                    else:
                        options.append('-XX:%s=%s' % (b,v))
                else:
                    print "Unknown JVM option type: %s" % a
        return options
