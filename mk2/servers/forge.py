from . import JarProvider

class Forge(JarProvider):
    base = 'http://files.minecraftforge.net/minecraftforge/minecraftforge-universal-{0}.zip'
    def work(self):
        for k in 'latest', 'recommended':
            self.add(('Forge', k.title()), (None, None), self.base.format(k))
        self.commit()

ref = Forge
