from twisted.internet import defer
from twisted.web.client import getPage

class Jar:
    def __init__(self, channel, artifact, url, channel_short=None, artifact_short=None):
        self.channel = channel
        self.artifact = artifact
        self.url     = url

        if channel_short is None:
            self.channel_short = channel.replace(' ', '-').lower()
        else:
            self.channel_short = channel_short

        if artifact_short is None:
            self.artifact_short = artifact.replace(' ', '-').lower()
        else:
            self.artifact_short = artifact_short

    def __repr__(self):
        return "%s-%s" % (self.channel_short, self.artifact_short)

class JarProvider:
    major = None
    def __init__(self, deferred):
        self.deferred = deferred
        self.response = []
        self.work()

    def get(self, url, callback):
        d = getPage(url)
        d.addCallback(callback)
        d.addErrback(self.error)

    def add(self, *a, **k):
        self.response.append(Jar(*a, **k))

    def commit(self, d=None):
        self.deferred.callback(self.response)

    def error(self, d=None):
        print d
        self.commit()

    def work(self):
        raise NotImplementedError

import vanilla, bukkit, tekkit, feed_the_beast

def get_available(callback):
    dd = []
    for mod in vanilla, bukkit, tekkit, feed_the_beast:
        d = defer.Deferred()
        mod.ref(d)
        dd.append(d)
    dd = defer.DeferredList(dd)

    callback2 = lambda data: [callback(d[1]) for d in data if d[0]]
    dd.addCallback(callback2)



