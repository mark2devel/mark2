from . import JenkinsJarProvider

class Libigot(JenkinsJarProvider):
    name = 'Libigot'
    base = 'http://build.libigot.org/'
    project = 'Libigot'

ref = Libigot
