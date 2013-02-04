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

        c_seperator  = (':', '=')
        c_newline    = ('\n', '\r', '')
        c_whitespace = (' ', '\t', '\f')
        c_escapes    = ('t','n','r','f')
        c_comment    = ('#','!')

        f = open(path)
        while True:
            #skip whitespace
            c = f.read(1)
            while c in c_whitespace:
                c = f.read(1)

            #finish on EOF
            if c == '':
                break

            #skip comments
            if c in c_comment:
                f.readline()
                continue

            #skip blank lines
            if c in c_newline:
                continue

            #read key
            k = ""
            while True:
                if c in c_newline:
                    break

                elif c in c_seperator + c_whitespace:
                    c = f.read(1)
                    break

                elif c == '\\':
                    c = f.read(1)
                    if c in c_escapes:
                        k += ('\\'+c).decode('string-escape')
                    elif c == 'u':
                        k += unichr(int(f.read(4)))
                    else:
                        k += c

                else:
                    k += c

                c = f.read(1)


            #skip whitespace
            while c in c_whitespace:
                c = f.read(1)

            #read value
            v = ""
            while True:
                if c in c_newline:
                    break

                elif c == '\\':
                    c = f.read(1)
                    if c in c_escapes:
                        v += ('\\'+c).decode('string-escape')
                    elif c == 'u':
                        v += unichr(int(f.read(4)))
                    else:
                        v += c
                else:
                    v += c

                c = f.read(1)

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
        f.close()

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
