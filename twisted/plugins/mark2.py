from zope.interface import implements

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
from twisted.application import internet

from manager import Manager


class Options(usage.Options):
    optParameters = [["dir", "d", ".", "The directory in which to find a server."]]


class Mark2ServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "mark2"
    description = "Minecraft server wrapper"
    options = Options

    def makeService(self, options):
        return Manager(str(options["dir"]))


serviceMaker = Mark2ServiceMaker()

