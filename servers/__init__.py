from twisted.internet import defer

from collections import namedtuple

jar = namedtuple("jar", ("channel", "channel_short", "version", "url"))

class JarProvider:
    major = None
    def __init__(self, deferred):
        self.deferred = deferred
        self.response = []
        self.work()

    def add(self, *d):
        self.response.append(jar(*d))

    def commit(self, d=None):
        self.deferred.callback(self.response)

    def error(self, d=None):
        self.deferred.errback()

    def work(self):
        raise NotImplementedError

import vanilla, bukkit

def get_available(callback):
    dd = []
    for mod in vanilla, bukkit:
        d = defer.Deferred()
        mod.ref(d)
        dd.append(d)
    dd = defer.DeferredList(dd)

    callback2 = lambda data: [callback(d[1]) for d in data if d[0]]
    dd.addCallback(callback2)



