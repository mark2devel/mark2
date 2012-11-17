from zope.interface import implements

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
from twisted.application import internet

from manager import Manager

import os
import sys

stderr = sys.stderr

class Options(usage.Options):
    optParameters = [["dir", "d", ".", "The directory in which to find a server."],
                     ["fd", None, None, "File descriptor to write startup output."]]


class Mark2ServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "mark2"
    description = "Minecraft server wrapper"
    options = Options

    def makeService(self, options):
        dir = str(options["dir"])
        fd = int(options["fd"])
        return Manager(dir, fd)


serviceMaker = Mark2ServiceMaker()

