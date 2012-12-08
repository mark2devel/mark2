import feedparser
from twisted.web.client import getPage

from plugins import Plugin

#Many thanks to Adam Wight for this
class FeedPoller(object):
    last_seen_id = None

    def parse(self, data):
        result = feedparser.parse(data)
        result.entries.reverse()
        skipping = True
        for entry in result.entries:
            if (self.last_seen_id == entry.id):
                skipping = False
            elif not skipping:
                yield entry

        if result.entries:
            self.last_seen_id = result.entries[-1].id

class RSS(Plugin):
    url            = ""
    check_interval = 60
    command        = "say {link} - {title}"
    
    def setup(self):
        self.poller = FeedPoller()
        
    def server_started(self, event):
        if self.url != "":
            self.repeating_task(self.check_feeds, self.check_interval)
    
    def check_feeds(self, event):
        d = getPage(self.url)
        d.addCallback(self.update_feeds)
    
    def update_feeds(self, data):
        for entry in self.poller.parse(data):
            self.send(self.command.format(**entry))
