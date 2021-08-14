import os
import sys

import treq
from twisted.internet import defer


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
        d = defer.Deferred()
        def handle_resp(resp):
           d = resp.json()
           d.addCallback(callback)
           d.addErrback(self.error)
        resp_defer = treq.get(str(url))
        resp_defer.addCallback(handle_resp)
        resp_defer.addErrback(self.error)
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
        self.get('{}job/{}/lastSuccessfulBuild/api/json'.format(self.base, self.project), self.handle_data)

    def handle_data(self, data):
        url = '{}job/{}/lastSuccessfulBuild/artifact/{}'.format(self.base, self.project, data['artifacts'][0]['relativePath'])
        self.add((self.name, 'Latest'), (None, None), url)
        self.commit()


modules = []
for m in ['vanilla']:
    try:
        name = "mk2.servers.{}".format(m)
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
                print("error: {}".format(data.value))
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
            listing += "  {} | {}\n".format(left.ljust(m), right)

        d_result.callback(listing.rstrip())

    d = get_raw()
    d.addCallbacks(got_results, d_result.errback)
    return d_result


def jar_get(name):
    d_result = defer.Deferred()
    global did_download
    did_download = True

    def err(_):
        global did_download
        did_download = False

    def got_results(results):
        global did_download
        for r in results:
            if name == '-'.join(r.name_short):
                filename = r.url.split('/')[-1]
                if os.path.exists(filename):
                    d_result.errback(Exception("File already exists!"))
                else:
                    print("Downloading file from {} to: {}".format(r.url, filename))
                    f_out = open(filename, "wb")
                    resp = treq.get(r.url, unbuffered=True)
                    resp.addCallback(treq.collect, f_out.write)
                    did_download = True
                    resp.addCallback(lambda _: d_result.callback(filename))
                    resp.addErrback(err)
                    resp.addBoth(lambda _: f_out.close())
        if not did_download:
            d_result.errback(Exception("{} is not available!".format(name)))

    d = get_raw()
    d.addCallback(got_results)
    return d_result
