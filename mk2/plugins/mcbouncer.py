from twisted.python import log
import urllib
import json

from twisted.web.client import HTTPClientFactory, getPage
HTTPClientFactory.noisy = False

from mk2.plugins import Plugin
from mk2.events import ServerOutput

class BouncerAPI:
    methods = ['addBan', 'removeBan', 'getBanReason', 'getIPBanReason', 'updateUser']
    def __init__(self, api_base, api_key, errback):
        self.api_key = api_key
        self.api_base = api_base
        self.errback = errback
    
    def __getattr__(self, method):
        if not method in self.methods:
            raise AttributeError
        
        def inner(*args, **kwargs):
            args = [urllib.quote(a.encode('utf8'), "") for a in args]
            callback = kwargs.get('callback', None)
            addr = '/'.join([self.api_base, method, self.api_key] + args)
            deferred = getPage(addr)
            if callback:
                deferred.addCallback(lambda d: callback(json.loads(str(d))))
                deferred.addErrback(self.errback)
        return inner

class MCBouncer(Plugin):
    api_base   = Plugin.Property(default='http://mcbouncer.com/api')
    api_key    = Plugin.Property(default=None)
    reason     = Plugin.Property(default="Banned by an operator")
    proxy_mode = Plugin.Property(default=False)
    
    def setup(self):
        self.bouncer = BouncerAPI(self.api_base, self.api_key, self.on_error)
        
        self.register(self.on_login,  ServerOutput, pattern='([A-Za-z0-9_]{1,16})\[/([0-9\.]+):\d+\] logged in with entity id .+')
        self.register(self.on_ban,    ServerOutput, pattern='\[([A-Za-z0-9_]{1,16}): Banned player ([A-Za-z0-9_]{1,16})\]')
        self.register(self.on_ban,    ServerOutput, pattern='Banned player ([A-Za-z0-9_]{1,16})')
        self.register(self.on_pardon, ServerOutput, pattern='\[[A-Za-z0-9_]{1,16}: Unbanned player ([A-Za-z0-9_]{1,16})\]')
        self.register(self.on_pardon, ServerOutput, pattern='Unbanned player ([A-Za-z0-9_]{1,16})')
    
    def on_error(self, error):
        self.console("Couldn't contact mcbouncer! %s" % error.getErrorMessage())
        
    def on_ban(self, event):
        g = event.match.groups()
        player = g[-1]
        issuer = g[0] if len(g) == 2 else 'console'
        o = self.bouncer.addBan(issuer, player, self.reason)
    
    def on_pardon(self, event):
        g = event.match.groups()
        self.bouncer.removeBan(g[0])
    
    def on_login(self, event):
        g = event.match.groups()
        self.bouncer.getBanReason(g[0], callback=lambda d: self.ban_reason(g[0], d))
        if not self.proxy_mode:
            self.bouncer.updateUser(g[0], g[1])
            self.bouncer.getIPBanReason(g[1], callback=lambda d: self.ip_ban_reason(g[0], d))
    
    def ban_reason(self, user, details):
        if details['is_banned']:
            self.send('kick %s Banned: %s' % (user, details['reason']))
    
    def ip_ban_reason(self, user, details):
        if details['is_banned']:
            self.send('kick %s Banned: %s' % (user, details['reason']))
