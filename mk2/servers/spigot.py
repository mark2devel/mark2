from . import JenkinsJarProvider

class Spigot(JenkinsJarProvider):
    name = 'Spigot'
    base = 'http://ci.md-5.net/'
    project = 'Spigot'

ref = Spigot
