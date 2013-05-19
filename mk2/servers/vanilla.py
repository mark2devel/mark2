import json

from . import JarProvider

class Vanilla(JarProvider):
    base = 'http://s3.amazonaws.com/Minecraft.Download/versions/'
    def work(self):
        self.get(self.base + 'versions.json', self.handle_data)

    def handle_data(self, data):
        for k, v in json.loads(data)['latest'].iteritems():
            self.add(('Vanilla', k.title()), (None, None), '{0}{1}/minecraft_server.{1}.jar'.format(self.base, v))
        self.commit()

ref = Vanilla
