import json

from . import JarProvider

class Vanilla(JarProvider):
    base = 'https://launchermeta.mojang.com/mc/game/'
    def work(self):
        self.get(self.base + 'version_manifest.json', self.handle_data)

    def handle_data(self, data):
        for k, v in json.loads(data)['latest'].items():
            self.add(('Vanilla', k.title()), (None, None), '{0}{1}/minecraft_server.{1}.jar'.format(self.base, v))
        self.commit()

ref = Vanilla
