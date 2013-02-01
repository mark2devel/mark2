def console_repr(e):
    s = u"%s %s " % (e.time, {'server': '|', 'mark2': '#', 'user': '>'}.get(e.source, '?'))
    if e.source == 'server' and e.level != 'INFO':
        s += u"[%s] " % e.level
    elif e.source == 'user':
        s += u"(%s) " % e.user
    
    s += u"%s" % e.data
    return s
