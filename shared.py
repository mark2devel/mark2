def console_repr(e):
    s = "%s %s " % (e.time, {'server': '|', 'mark2': '#', 'user': '>'}.get(e.source, '?'))
    if e.source == 'server' and e.level != 'INFO':
        s += "[%s] " % e.level
    elif e.source == 'user':
        s += "(%s) " % e.user
    
    s += "%s" % e.data
    return s
