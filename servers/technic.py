from twisted.internet.defer import DeferredList
from servers import JarProvider

class Technic(JarProvider):
    base = 'http://mirror.technicpack.net/Technic/'
    packs   = (
        ('Tekkit Classic', 'tekkit',     'Tekkit_Server_{version}.zip'),
        ('Tekkit Lite',    'tekkitlite', 'Tekkit_Lite_Server_{version}.zip'),
        ('Voltz',          'voltz',      'Voltz_Server_v{version}.zip'))
    builds = ('recommended', 'latest')

    def work(self):
        d = []
        for name, dir, fn in self.packs:
            d.append(self.get(self.base + dir + '/modpack.yml', lambda d, name=name, dir=dir, fn=fn: self.handle_data(d, name, dir, fn)))
        d = DeferredList(d)
        d.addCallback(self.commit)

    def handle_data(self, data, name, dir, fn):
        for line in data.split("\n"):
            if line == "" or line[0] in (" ", "\t"):
                break

            line = line.split(": ", 2)
            if line[0] in self.builds:
                self.add(('Technic', name, line[0].title()), (None, None, None), self.base+'servers/'+dir+'/'+fn.format(version=line[1]))

ref = Technic