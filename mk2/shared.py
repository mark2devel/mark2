import os
import pkg_resources


def open_resource(name):
    return pkg_resources.resource_stream('mk2', name)


_config_base = None


_config_try = [os.path.join(os.path.expanduser("~"), ".config", "mark2"), "/etc/mark2"]
if "VIRTUAL_ENV" in os.environ:
    _config_try.insert(0, os.path.join(os.environ["VIRTUAL_ENV"], ".config", "mark2"))


def find_config(name):
    global _config_base
    if not _config_base:
        for path in _config_try:
            if os.path.exists(path):
                _config_base = path
                print "use {0}".format(path)
                break

    if not _config_base:
        for path in _config_try:
            try:
                os.makedirs(path)
                _config_base = path
                print "use {0}".format(path)
                break
            except OSError:
                pass

    if not _config_base:
        raise ValueError

    return os.path.join(_config_base, name)


def console_repr(e):
    s = u"%s %s " % (e['time'], {'server': '|', 'mark2': '#', 'user': '>'}.get(e['source'], '?'))
    if e['source'] == 'server' and e['level'] != 'INFO':
        s += u"[%s] " % e['level']
    elif e['source'] == 'user':
        s += u"(%s) " % e['user']
    
    s += u"%s" % e['data']
    return s
