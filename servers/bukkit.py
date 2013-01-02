import json

from twisted.web.client import getPage

from servers import JarProvider

class Bukkit(JarProvider):
    def work(self):
        d = getPage('http://dl.bukkit.org/api/1.0/downloads/channels/', headers={'Accept': 'application/json'})
        d.addCallback(self.handle_channels)
        d.addBoth(self.commit)

    def handle_channels(self, data):
        data = json.loads(data)
        for channel in data['results']:
            name = channel['name']
            slug = channel['slug']
            self.add('Bukkit '+name, 'bukkit-'+slug, None, 'http://dl.bukkit.org/latest-%s/craftbukkit.jar' % slug)

ref = Bukkit