from xml.dom import minidom

from twisted.web.client import getPage

from servers import JarProvider

class Vanilla(JarProvider):
    base = 'http://assets.minecraft.net/'
    target = '/minecraft_server.jar'
    def work(self):
        self.add('Vanilla Stable', 'vanilla-stable', None, 'https://s3.amazonaws.com/MinecraftDownload/launcher/minecraft_server.jar')
        d = getPage(self.base)
        d.addCallback(self.handle_latest)
        d.addBoth(self.commit)

    def handle_latest(self, data):
        dom = minidom.parseString(data)
        child = lambda n, name: n.getElementsByTagName(name)[0].childNodes[0].data

        c_date = 0
        c_path = None
        for n in dom.getElementsByTagName("Contents"):
            path = child(n, 'Key')
            if path.endswith(self.target):
                date = child(n, 'LastModified')
                if date > c_date:
                    c_date = date
                    c_path = path

        if not c_path is None:
            c_name = c_path[:-len(self.target)]
            c_name = c_name.replace("_", ".")
            self.add('Vanilla Latest', 'vanilla-latest', c_name, self.base + c_path)

ref = Vanilla