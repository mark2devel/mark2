

from servers import JarProvider

class Spigot(JarProvider):
    base = 'http://ci.md-5.net/job/Spigot/lastStableBuild/artifact/Spigot/target/spigot.jar'

    def work(self):
        self.add(('Spigot', 'Latest'), (None, None), self.base)
        self.commit()

ref = Spigot