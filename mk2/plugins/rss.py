import feedparser
import re
from twisted.web.client import getPage

from mk2.plugins import Plugin

reddit_link = re.compile('http://(?:www\.)?redd(?:\.it/|it\.com/(?:tb|(?:r/[\w\.]+/)?comments)/)(\w+)(/.+/)?(\w{7})?')


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
    url = Plugin.Property(default="")
    check_interval = Plugin.Property(default=60)
    command = Plugin.Property(default="say {link} - {title}")
    
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
            m = reddit_link.match(entry['link'])
            if m:
                entry['link'] = "http://redd.it/" + m.group(1)
            self.send_format(self.command, parseColors=True, **entry)
