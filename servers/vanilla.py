from xml.dom import minidom

from servers import JarProvider

class Vanilla(JarProvider):
    base = 'http://assets.minecraft.net/'
    target = '/minecraft_server.jar'
    def work(self):
        self.add('Vanilla', 'Stable', 'https://s3.amazonaws.com/MinecraftDownload/launcher/minecraft_server.jar')
        self.get(self.base, self.handle_latest)

    def handle_latest(self, data):
        child = lambda n, name: n.getElementsByTagName(name)[0].childNodes[0].data

        dom = minidom.parseString(data)

        c_date = 0
        c_path = None
        for node in dom.getElementsByTagName("Contents"):
            path = child(node, 'Key')
            if path.endswith(self.target):
                date = child(node, 'LastModified')
                if date > c_date:
                    c_date = date
                    c_path = path

        if not c_path is None:
            self.add('Vanilla', 'Latest', self.base + c_path)

        self.commit()

ref = Vanilla