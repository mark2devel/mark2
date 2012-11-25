import re

from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor

class SnoopResource(Resource):
    isLeaf = True
    def render_POST(self, request):
        d = {}
        for k, v in request.args.iteritems():
            v = v[0]
            if re.match('^\d+$', v):
                v = int(v)
            if v in ('true', 'false'):
                v = v == 'true'
            d[k] = v
        self.callback(d)

def Snoop(callback, port):
    resource = SnoopResource()
    resource.callback = callback
    factory = Site(resource)
    reactor.listenTCP(port, factory)
    return factory
