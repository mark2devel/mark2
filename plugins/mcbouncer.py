import urllib
import json
from twisted.web.client import getPage

from plugins import Plugin, Interest, register

class BouncerAPI:
    methods = ['addBan', 'removeBan', 'getBanReason', 'getIPBanReason', 'updateUser']
    def __init__(self, API_BASE, API_KEY):
        self.API_KEY = API_KEY
        self.API_BASE = API_BASE
    
    def __getattr__(self, method):
        if not method in self.methods:
            raise AttributeError
        
        def inner(*args, **kwargs):
            args = [urllib.quote(a, "") for a in args]
            callback = kwargs.get('callback', None)
            addr = '/'.join([self.API_BASE, method, self.API_KEY] + args)
            deferred = getPage(addr)
            if callback:
                deferred.addCallback(lambda d: callback(json.loads(str(d))))
        return inner

class MCBouncer(Plugin):
    api_base   = 'http://mcbouncer.com/api'
    api_key    = None
    reason     = "Banned by an operator"
    proxy_mode = False
    
    def setup(self):
        self.bouncer = BouncerAPI(self.api_base, self.api_key)
        
        self.register(self.on_login,  ServerOutput, pattern='([A-Za-z0-9_]{1,16})\[/([0-9\.]+):\d+\] logged in with entity id .+')
        self.register(self.on_ban,    ServerOutput, pattern='\[([A-Za-z0-9_]{1,16}): Banned player ([A-Za-z0-9_]{1,16})\]')
        self.register(self.on_ban,    ServerOutput, pattern='') #TODO: console version
        self.register(self.on_pardon, ServerOutput, pattern='\[([A-Za-z0-9_]{1,16}): Unbanned player ([A-Za-z0-9_]{1,16})\]')
        self.register(self.on_pardon, ServerOutput, pattern='') #TODO: console version
    
        
    def on_ban(self, event):
        g = event.match.groups()
        o = self.bouncer.addBan(g[0], g[1], self.reason)
    
    def on_pardon(self, match):
        g = event.match.groups()
        self.bouncer.removeBan(g[1])
    
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
