import os
import pkg_resources


def open_resource(name):
    return pkg_resources.resource_stream('mk2', name)


_config_found = False


if "MARK2_CONFIG_DIR" in os.environ:
    _config_base = os.environ["MARK2_CONFIG_DIR"]
elif "VIRTUAL_ENV" in os.environ:
    _config_base = os.path.join(os.environ["VIRTUAL_ENV"], ".config", "mark2")
elif __file__.startswith('/home/'):
    _config_base = os.path.join(os.path.expanduser("~"), ".config", "mark2")
else:
    _config_base = os.path.join(os.path.join("/etc/mark2"))


def find_config(name, create=True, ignore_errors=False):
    global _config_base, _config_found
    if not _config_found:
        if os.path.exists(_config_base):
            _config_found = True

    if create and not _config_found:
        try:
            os.makedirs(_config_base)
            _config_found = True
        except OSError:
            pass

    if not ignore_errors and not _config_found:
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
