from . import JarProvider

class Nukkit(JarProvider):
    base = 'http://www.nukkit-project.fr/downloads/'
    def work(self):
        self.add(('Nukkit', 'Stable'), (None, None), self.base + 'craftnukkit')
        self.add(('Nukkit', 'Beta'),   (None, None), self.base + 'beta/craftnukkit')
        self.commit()

ref = Nukkit
