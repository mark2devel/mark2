import json
from . import JarProvider

class Technic(JarProvider):
    api_base = 'http://solder.technicpack.net/api/modpack/?include=full'
    packs   = (
        ('bigdig',     'BigDigServer-v{0}.zip'),
        ('tekkit',     'Tekkit_Server_{0}.zip'),
        ('tekkitlite', 'Tekkit_Lite_Server_{0}.zip'),
        ('voltz',      'Voltz_Server_v{0}.zip'))
    builds = ('recommended', 'latest')

    def work(self):
        self.get(self.api_base, self.handle_data)

    def handle_data(self, data):
        data = json.loads(data)
        base = data['mirror_url']
        for name, server in self.packs:
            mod = data['modpacks'][name]
            title = mod['display_name']
            title = 'Tekkit Classic' if title == 'Tekkit' else title
            for build in self.builds:
                self.add(('Technic', title, build.title()), (None, None, None),
                          base + 'servers/' + name + '/' + server.format(mod[build]))
        self.commit()

ref = Technic
