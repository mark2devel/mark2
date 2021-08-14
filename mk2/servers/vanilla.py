import json
import treq
from twisted.internet import defer

from . import JarProvider


class Vanilla(JarProvider):
    base = 'https://launchermeta.mojang.com/mc/game/'
    url = ''
    def work(self):
        self.get(self.base + 'version_manifest.json', self.handle_data)

    def handle_data(self, data):
        deferred_list = []

        def got_json(_json_data, ver_type):
            self.add(('Vanilla', ver_type.title()), (None, None), _json_data["downloads"]["server"]["url"])

        def got_version_info(_data, ver_type):
            json_defer = _data.json()
            json_defer.addCallback(got_json, ver_type)

        for k, v in data['latest'].items():
            for version in data["versions"]:
                if version["id"].startswith(v) and version["type"] == k:
                    print("Getting info for: {}-{} with URL: {}".format(v, k, version["url"]))
                    resp_d = treq.get(version["url"])
                    resp_d.addCallback(got_version_info, k)
                    resp_d.addErrback(self.error)
                    deferred_list.append(resp_d)
                    break
        
        d = defer.DeferredList(deferred_list)
        d.addCallback(self.commit)

ref = Vanilla
