from zope.interface import implements

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker

from manager import Manager

import sys

stderr = sys.stderr


class Options(usage.Options):
    optParameters = [["dir", None, "", "The directory in which to find a server."],
                     ["fd", None, None, "File descriptor to write startup output."],
                     ["sockets", None, "/tmp/mark2/", "Socket base directory"],
                     ["jarfile", None, None, "Name of the server jar"]]


class Mark2ServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "mark2"
    description = "Minecraft server wrapper"
    options = Options

    def makeService(self, options):
        fd = int(options["fd"]) if options["fd"] else None
        return Manager(options["dir"],
                       initial_output=fd,
                       socketdir=options["sockets"],
                       jarfile=options["jarfile"])


serviceMaker = Mark2ServiceMaker()
