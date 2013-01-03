from servers import JarProvider

class Tekkit(JarProvider):
    base = 'http://mirror.technicpack.net/Technic/'
    artifacts = ('recommended', 'latest')

    def work(self):
        self.get(self.base + 'tekkit/modpack.yml', self.handle_data)

    def handle_data(self, data):
        for line in data.split("\n"):
            if line == "" or line[0] in (" ", "\t"):
                break

            line = line.split(": ", 2)
            if line[0] in self.artifacts:
                self.add('Tekkit', line[0].title(), self.base+'servers/tekkit/Tekkit_Server_' + line[1] + '.zip')

        self.commit()

ref = Tekkit