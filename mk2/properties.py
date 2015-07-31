import os
import re
import shlex
import zipfile


def load(cls, *files):
    o = None
    for f in files:
        if isinstance(f, basestring):
            if os.path.isfile(f):
                with open(f) as f:
                    o = cls(f, o)
        else:
            o = cls(f, 0)
    return o


def load_jar(jar, *path):
    path = list(path)
    while path:
        try:
            z = zipfile.ZipFile(jar, 'r')
            o = Lang(z.open(path.pop(0), 'r'))
            z.close()
            return o
        except KeyError:
            pass
    return None


class Properties(dict):
    def __init__(self, f, parent=None):
        dict.__init__(self)

        if parent:
            self.update(parent)
            self.types = dict(parent.types)
        else:
            self.types = {}

        decoder = {
            'int': int,
            'bool': lambda a: a == 'true',
            'string': lambda a: a
        }

        c_seperator  = (':', '=')
        c_whitespace = (' ', '\t', '\f')
        c_escapes    = ('t','n','r','f')
        c_comment    = ('#','!')

        r_unescaped  = '(?<!\\\\)(?:\\\\\\\\)*'
        r_whitespace = '[' + re.escape(''.join(c_whitespace)) + ']*'
        r_seperator  = r_unescaped + r_whitespace + r_unescaped + '[' + re.escape(''.join(c_seperator + c_whitespace)) + ']'

        #This handles backslash escapes in keys/values
        def parse(input):
            token = list(input)
            out = u""
            uni = False
            while len(token) > 0:
                c = token.pop(0)
                if c == '\\':
                    try:
                        c = token.pop(0)
                        if c in c_escapes:
                            out += ('\\'+c).decode('string-escape')
                        elif c == 'u':
                            b = ""
                            for i in range(4):
                                b += token.pop(0)
                            out += unichr(int(b, 16))
                            uni = True
                        else:
                            out += c
                    except IndexError:
                        raise ValueError("Invalid escape sequence in input: %s" % input)
                else:
                    out += c

            if not uni:
                out = out.encode('ascii')
            return out

        d = f.read()

        #Deal with Windows / Mac OS linebreaks
        d = d.replace('\r\n','\n')
        d = d.replace('\r', '\n')
        #Strip leading whitespace
        d = re.sub('(?m)\n\s*', '\n', d)
        #Split logical lines
        d = re.split('(?m)' + r_unescaped + '\n', d)

        for line in d:
            #Strip comments and empty lines
            if line == '' or line[0] in c_comment:
                continue

            #Strip escaped newlines
            line = re.sub('(?m)' + r_unescaped + '(\\\\\n)', '', line)
            assert not '\n' in line

            #Split into k,v
            x = re.split(r_seperator, line, maxsplit=1)

            #No seperator, parse as empty value.
            if len(x) == 1:
                k, v = x[0], ""
            else:
                k, v = x

            k = parse(k).replace('-', '_')
            v = parse(v)

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

    def get_by_prefix(self, prefix):
        for k, v in self.iteritems():
            if k.startswith(prefix):
                yield k[len(prefix):], v


class Mark2Properties(Properties):
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

        return [(n, plugins[n]) for n in sorted(enabled)]

    def get_service(self, service):
        return self.get_by_prefix('mark2.service.{0}.'.format(service))

    def get_jvm_options(self):
        options = []
        for k, v in self.iteritems():
            m = re.match('^java\.cli\.([^\.]+)\.(.+)$', k)
            if m:
                a, b = m.groups()
                if a == 'D':
                    if type(v) == bool:
                        v = str(v).lower()
                    options.append('-D%s=%s' % (b, v))
                elif a == 'X':
                    if type(v) == bool:
                        v = str(v).lower()
                    options.append('-X%s%s' % (b, v))
                elif a == 'XX':
                    if type(v) == bool:
                        options.append('-XX:%s%s' % ('+' if v else '-', b))
                    else:
                        options.append('-XX:%s=%s' % (b, v))
                else:
                    print "Unknown JVM option type: %s" % a
        if self.get('java.cli_extra', '') != '':
            options.extend(shlex.split(self['java.cli_extra']))
        return options
    
    def get_format_options(self):
        options = {}
        for k, v in self.iteritems():
            m = re.match('^mark2\.format\.(.*)$', k)
            if m:
                options[m.group(1)] = v
        return options

    def get_umask(self, ext):
        return int(str(self['mark2.umask.' + ext]), 8)

class ClientProperties(Properties):
    def get_palette(self):
        palette = []
        for k, v in self.get_by_prefix('theme.%s.' % self['theme']):
            palette.append([k,] + [t.strip() for t in v.split(',')])
        return palette

    def get_player_actions(self):
        return self['player_actions'].split(',')

    def get_player_reasons(self):
        return self.get_by_prefix('player_actions.reasons.')

    def get_apps(self):
        return self.get_by_prefix('stats.app.')

    def get_interval(self, name):
        return self['task.%s' % name]

class Lang(Properties):
    def get_deaths(self):
        seen = []
        for k, v in self.get_by_prefix('death.'):
            if not v in seen:
                seen.append(v)
                regex = reduce(lambda a, r: a.replace(*r),
                               ((r"\%{0}\$s".format(i + 1),
                                 "(?P<{0}>[A-Za-z0-9]{{1,32}})".format(x))
                                for i, x in enumerate(("username", "killer", "weapon"))),
                               re.escape(v))
                format = reduce(lambda a, r: a.replace(*r),
                                (("%{0}$s".format(i + 1),
                                  "{{{0}}}".format(x))
                                 for i, x in enumerate(("username", "killer", "weapon"))),
                                v)
                yield k, ("^{0}$".format(regex), format)
