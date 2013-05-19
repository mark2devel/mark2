from zope.interface import implements

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker

from mk2.manager import Manager

import sys

stderr = sys.stderr


class Options(usage.Options):
    optParameters = [["shared-path", None, "/tmp/mark2/", "mark2 temp directory"],
                     ["server-name", None, None, "Name of the server."],
                     ["server-path", None, None, "Socket base directory"],
                     ["jar-file",    None, None, "Name of the server jar"]]


class Mark2ServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "mark2"
    description = "minecraft server wrapper"
    options = Options

    def makeService(self, options):
        return Manager(
            options['shared-path'],
            options['server-name'],
            options['server-path'],
            options['jar-file'])


serviceMaker = Mark2ServiceMaker()
