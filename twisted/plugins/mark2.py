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
    optParameters = [["dir", None, "", "The directory in which to find a server."],
                     ["fd", None, None, "File descriptor to write startup output."],
                     ["sockets", None, "/tmp/mcpitch/", "Socket base directory"],
                     ["jarfile", None, None, "Name of the server jar"]]


class Mark2ServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "mark2"
    description = "Minecraft server wrapper"
    options = Options

    def makeService(self, options):
        fd = int(options["fd"])
        return Manager(options["dir"],
                       output=fd,
                       socketdir=options["sockets"],
                       jarfile=options["jarfile"])


serviceMaker = Mark2ServiceMaker()

