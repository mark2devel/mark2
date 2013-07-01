import json
import sys

from twisted.internet import reactor, defer
from twisted.web.client import getPage, HTTPClientFactory

try:
    from twisted.internet import ssl
except ImportError:
    ssl = None


class Jar:
    def __init__(self, name_long, name_short, url):
        self.name_long  = list(name_long)
        self.name_short = list(name_short)
        self.url = str(url)

        for i, l in enumerate(self.name_long):
            l = l.replace(' ', '-').lower()
            if i > len(self.name_short):
                self.name_short.append(l)
            elif self.name_short[i] is None:
                self.name_short[i] = l

    def __repr__(self):
        return '-'.join(self.name_short)


class JarProvider:
    major = None

    def __init__(self, deferred):
        self.deferred = deferred
        self.response = []
        self.work()

    def get(self, url, callback):
        d = getPage(str(url))
        d.addCallback(callback)
        d.addErrback(self.error)
        return d

    def add(self, *a, **k):
        self.response.append(Jar(*a, **k))

    def commit(self, d=None):
        self.deferred.callback(self.response)

    def error(self, d=None):
        self.deferred.errback(d)

    def work(self):
        raise NotImplementedError


class JenkinsJarProvider(JarProvider):
    base = None
    project = None
    name = None

    def work(self):
        self.get('{0}job/{1}/lastSuccessfulBuild/api/json'.format(self.base, self.project), self.handle_data)

    def handle_data(self, data):
        data = json.loads(data)
        url = '{0}job/{1}/lastSuccessfulBuild/artifact/{2}'.format(self.base, self.project, data['artifacts'][0]['relativePath'])
        self.add((self.name, 'Latest'), (None, None), url)
        self.commit()


modules = []
for m in ['bukkit', 'feed_the_beast', 'forge', 'libigot', 'mcpcplus', 'nukkit', 'spigot', 'technic', 'vanilla']:
    try:
        name = "mk2.servers.{0}".format(m)
        __import__(name)
        modules.append(sys.modules[name])
    except ImportError:
        pass


def get_raw():
    d_results = defer.Deferred()
    dd = [defer.succeed([])]
    for mod in modules:
        d = defer.Deferred()
        mod.ref(d)
        dd.append(d)
    dd = defer.DeferredList(dd, consumeErrors=True)

    def callback2(raw):
        results = []
        for ok, data in raw:
            if ok:
                results.extend(data)
            else:
                print "error: %s" % data.value
        d_results.callback(results)

    dd.addCallback(callback2)
    return d_results


def jar_list():
    d_result = defer.Deferred()
    def got_results(results):
        listing = ""
        o = []
        m = 0
        for r in results:
            left  = '-'.join(r.name_short)
            right = ' '.join(r.name_long)
            m = max(m, len(left))
            o.append((left, right))

        for left, right in sorted(o):
            listing += "  %s | %s\n" % (left.ljust(m), right)

        d_result.callback(listing.rstrip())

    d = get_raw()
    d.addCallbacks(got_results, d_result.errback)
    return d_result


def jar_get(name):
    d_result = defer.Deferred()

    def got_data(factory, data):
        filename = factory.path.split('/')[-1]

        #parse the Content-Disposition header
        dis = factory.response_headers.get('content-disposition', None)
        if dis:
            dis = dis[0].split(';')
            if dis[0] == 'attachment':
                for param in dis[1:]:
                    key, value = param.strip().split('=')
                    if key == 'filename':
                        filename = value.replace("\"", "")

        d_result.callback((filename, data))

    def got_results(results):
        for r in results:
            if name == '-'.join(r.name_short):
                factory = HTTPClientFactory(r.url)

                if factory.scheme == 'https':
                    if ssl:
                        reactor.connectSSL(factory.host, factory.port, factory, ssl.ClientContextFactory())
                    else:
                        d_result.errback(Exception("{0} is not available because this installation does not have SSL support!".format(name)))
                else:
                    reactor.connectTCP(factory.host, factory.port, factory)

                factory.deferred.addCallback(lambda d: got_data(factory, d))
                factory.deferred.addErrback(d_result.errback)
                return

        d_result.errback(Exception("{0} is not available!".format(name)))

    d = get_raw()
    d.addCallbacks(got_results, d_result.errback)
    return d_result
