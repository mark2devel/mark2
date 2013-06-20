from mk2.plugins import Plugin
from mk2.events import ServerEvent, EventPriority

from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList
from twisted.mail import smtp, relaymanager
from twisted.web.client import getPage

from cStringIO import StringIO
from email.mime.text import MIMEText
from urllib import urlencode
import re

_endpoint = {}
_plugin = None


def endpoint(s):
    def _wrapper(cls):
        _endpoint[s] = cls
        cls.scheme = s
        return cls
    return _wrapper


class Endpoint(object):
    causes = "*"
    priority = "*"
    
    def __init__(self, plugin, uri):
        pass
        
    def push(self, event):
        pass
    
    def filter(self, event):
        if self.priority != "*":
            if int(self.priority) > event.priority:
                return False
        if self.causes != "*":
            for cause in self.causes.split(","):
                if cause == event.cause:
                    return True
                if cause.endswith("/") and event.cause.startswith(cause):
                    return True
            return False
        return True
    
    def wait(self, defer):
        def done_waiting(a):
            _plugin.pending.remove(defer)
            return a
        _plugin.pending.add(defer)
        defer.addBoth(done_waiting)
    
    def __str__(self):
        return "<{0} {1} causes={2} priority={3}>".format(self.__class__.__name__,
                                                          self.url,
                                                          self.causes, self.priority)
    
    
class HTTPEndpoint(Endpoint):
    method = "POST"
    postdata = {}
    
    def push(self, event):
        self.setup(event)
        
        defer = getPage(self.endpoint,
                        method=self.method,
                        postdata=urlencode(self.postdata),
                        headers={"Content-type": "application/x-www-form-urlencoded"})
        
        self.wait(defer)


@endpoint("nma")
class NMAEndpoint(HTTPEndpoint):
    endpoint = "https://www.notifymyandroid.com/publicapi/notify"
    method = "POST"
    
    def __init__(self, plugin, url):
        self.postdata = {
            "apikey":      url,
            "application": "mark2: {0}".format(plugin.parent.server_name),
        }
    
    def setup(self, event):
        self.postdata.update(priority=event.priority,
                             event=event.friendly,
                             description=event.data)


@endpoint("prowl")
class ProwlEndpoint(HTTPEndpoint):
    endpoint = "https://api.prowlapp.com/publicapi/add"
    method = "POST"
    
    def __init__(self, plugin, url):
        self.postdata = {
            "apikey":      url,
            "application": "mark2: {0}".format(plugin.parent.server_name),
        }
    
    def setup(self, event):
        self.postdata.update(priority=event.priority,
                             event=event.friendly,
                             description=event.data)


@endpoint("pushover")
class PushoverEndpoint(HTTPEndpoint):
    endpoint = "https://api.pushover.net/1/messages.json"
    method = "POST"
    device = None
    
    def __init__(self, plugin, url):
        if not plugin.pushover_token:
            raise Exception("pushover token is not configured")
        self.postdata = {
            "user":  url,
            "token": plugin.pushover_token,
        }
    
    def setup(self, event):
        self.postdata.update(priority=max(-1, event.priority),
                             title=event.friendly,
                             message=event.data)
        if self.device:
            self.postdata["device"] = self.device


@endpoint("smtp")
class SMTPEndpoint(Endpoint):
    def __init__(self, plugin, url):
        self.smtp_host, self.smtp_user, self.smtp_password =\
            plugin.email_smtp_server, plugin.email_smtp_user, plugin.email_smtp_password
        self.smtp_security = plugin.email_smtp_security

        if ':' in self.smtp_host:
            host = self.smtp_host.split(':')
            self.smtp_host, self.smtp_port = host[0], int(host[1])
        else:
            self.smtp_port = 25

        self.from_addr = plugin.email_address
        self.from_name = "mark2: {0}".format(plugin.parent.server_name)
        self.to_addr = url
        
    def getMailExchange(self, host):
        mxc = relaymanager.MXCalculator()
        def cbMX(mxRecord):
            return str(mxRecord.name)
        return mxc.getMX(host).addCallback(cbMX)

    def sendEmail(self, from_, from_name, to, msg_, subject=""):
        def send(host, user=None, pw=None, require_security=False):
            msg = MIMEText(msg_)
            msg['From'] = "\"{0}\" <{1}>".format(from_name, from_)
            msg['To'] = to
            msg['Subject'] = subject
            msgfile = StringIO(msg.as_string())
            d = Deferred()
            factory = smtp.ESMTPSenderFactory(user, pw, from_, to, msgfile, d,
                                              requireAuthentication=(user is not None),
                                              requireTransportSecurity=require_security)
            reactor.connectTCP(host, self.smtp_port, factory)
            self.wait(d)
            return d
        if self.smtp_host:
            return send(self.smtp_host, self.smtp_user, self.smtp_password, self.smtp_security)
        else:
            return self.getMailExchange(to.split("@")[1]).addCallback(send)
    
    def push(self, event):
        defer = self.sendEmail(self.from_addr, self.from_name, self.to_addr, event.data, event.friendly)
        
        self.wait(defer)


class Push(Plugin):
    endpoints           = Plugin.Property(default="")

    email_address       = Plugin.Property(default="mark2@fantastic.minecraft.server")
    email_smtp_server   = Plugin.Property(default="")
    email_smtp_user     = Plugin.Property(default="")
    email_smtp_password = Plugin.Property(default="")
    email_smtp_security = Plugin.Property(default=False)

    pushover_token      = Plugin.Property(default="")
    
    def setup(self):
        global _plugin
        _plugin = self
        
        self.pending = set()
        
        self.configure_endpoints()
        
        self.register(self.send_alert, ServerEvent, priority=EventPriority.MONITOR)
        
        self.eventid = reactor.addSystemEventTrigger('before', 'shutdown', self.finish)
    
    def teardown(self):
        reactor.removeSystemEventTrigger(self.eventid)
    
    def finish(self):
        return DeferredList(list(self.pending))
    
    def configure_endpoints(self):
        eps = self.endpoints.split("\n")
        self._endpoints = []
        for ep in eps:
            if not ep.strip():
                continue
            try:
                bits = re.split("\s+", ep)
                url, md = bits[0], bits[1:]
                scheme, ee = re.split(":(?://)?", url)
                if scheme not in _endpoint:
                    self.console("undefined endpoint requested: {0}".format(url))
                    continue
                cls = _endpoint[scheme]
                inst = cls(self, ee)
                inst.url = url
                for k, v in [d.split("=") for d in md]:
                    setattr(inst, k, v)
                self._endpoints.append(inst)
            except Exception as e:
                self.console("push: ERROR ({0}) adding endpoint: {1}".format(e, ep))
    
    def send_alert(self, event):
        for ep in self._endpoints:
            if ep.filter(event):
                ep.push(event)
