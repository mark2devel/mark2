import json

from . import JarProvider


class Bukkit(JarProvider):
    def work(self):
        self.get('http://dl.bukkit.org/api/1.0/downloads/channels/?_accept=application/json', self.handle_channels)

    def handle_channels(self, data):
        data = json.loads(data)
        for channel in data['results']:
            name = channel['name']
            slug = channel['slug']
            self.add(('Bukkit', name), (None, slug), 'http://dl.bukkit.org/latest-%s/craftbukkit.jar' % slug)

        self.commit()

ref = Bukkit
