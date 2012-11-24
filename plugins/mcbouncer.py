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
            addr = '/'.join([self.API_BASE, method, self.API_KEY] + args)
            deferred = getPage(addr)
            if kwargs and 'callback' in kwargs:
                deferred.addCallback(lambda d: kwargs['callback'](json.loads(d)))
            return addr
        return inner

class MCBouncer(Plugin):
    api_base = 'http://mcbouncer.com/api'
    api_key  = None
    reason   = ""
    
    proxy_mode = False
    
    def setup(self):
        self.bouncer = BouncerAPI(self.api_base, self.api_key)
        
    @register(Interest, 'INFO', r'\[([A-Za-z0-9_]{1,16}): Banned player ([A-Za-z0-9_]{1,16})\]')
    def on_ban(self, match):
        self.console("banned...")
        o = self.bouncer.addBan(match.group(1), match.group(2), self.reason)
        self.console(o)
    
    @register(Interest, 'INFO', r'\[([A-Za-z0-9_]{1,16}): Unbanned player ([A-Za-z0-9_]{1,16})\]')
    def on_pardon(self, match):
        self.console("unbanned...")
        self.bouncer.removeBan(match.group(2))
    
    @register(Interest, 'INFO', '([A-Za-z0-9_]{1,16})\[/([0-9\.]+):\d+\] logged in with entity id .+')
    def on_login(self, match):
        self.console("user logged in!")
        self.bouncer.getBanReason(match.group(1), callback=self.ban_reason)
        if not self.proxy_mode:
            self.bouncer.updateUser(match.group(1), match.group(2))
            self.bouncer.getIPBanReason(match.group(2), callback=lambda d: self.ip_ban_reason(m.group(1), d))
    
    def ban_reason(self, details):
        if details['is_banned']:
            self.send('kick %s Banned: %s' % (details['user'], details['reason']))
    
    def ip_ban_reason(self, user, details):
        if details['is_banned']:
            self.send('kick %s Banned: %s' % (user, details['reason']))
