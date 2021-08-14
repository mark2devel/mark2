import treq
from twisted.internet import defer

from . import JarProvider


class Vanilla(JarProvider):
    base = 'https://launchermeta.mojang.com/mc/game/'
    url = ''
    def work(self):
        self.get(self.base + 'version_manifest.json', self.handle_data)

    @defer.inlineCallbacks
    def handle_data(self, data):
        deferred_list = []
        def got_json(_json_data, ver_type):
            self.add(('Vanilla', ver_type.title()), (None, None), _json_data["downloads"]["server"]["url"])

        for k, v in data['latest'].items():
            for version in data["versions"]:
                if version["id"].startswith(v) and version["type"] == k:
                    print("Getting info for: {}-{} with URL: {}".format(v, k, version["url"]))
                    d = treq.get(version["url"])
                    resp = yield d
                    _json = yield resp.json()
                    got_json(_json, k)
                    deferred_list.append(d)
                    break
        
        d = defer.DeferredList(deferred_list)
        d.addCallback(self.commit)
        d.addErrback(d.errback)

ref = Vanilla
