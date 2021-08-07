import json
from http import client

from mk2.events import EventPriority, ServerEvent, ServerStarted, ServerStopped, ServerStopping, ServerStarting
from mk2.plugins import Plugin
from mk2.shared import decode_if_bytes


class WebhookBuilder:
class WebhookObject(dict):
    def __init__(self, username):
        self.username = username
        self.content = ""
        self.embeds = []

    def set_content(self, content):
        self.content = content
    
    def add_embed(self, title, fields=[]):
        """ Creates an embed object with the specified title and optional list of fields"""
        self.embeds.append({"title": title, "fields": fields})
    
    def add_embed_field(self, title, name, value, inline=False):
        """ Adds a field to the embed matching the title given """
        for embed in self.embeds:
            if embed["title"] == title:
                embed["fields"].append({"name": name, "value": value, "inline": inline})
                break
    

class Discord(Plugin):
    webhook_url = Plugin.Property(required=True)
    webhook_name = Plugin.Property(default="mark2")
    server_name = Plugin.Property(required=True)

    stop_types = {
        0: "Terminate",
        1: "Restart",
        2: "Hold"
    }

    def setup(self):
        # Strip the address part of the url from the URL to just leave the api call
        # if self.webhook_url.find("https://discord.com/") != -1:
        #     self.webhook_url = self.webhook_url.replace("https://discord.com/", "/")

        self.register(self.handle_server_event,    ServerEvent, priority=EventPriority.MONITOR)
        self.register(self.handle_server_starting, ServerStarting)
        self.register(self.handle_server_started,  ServerStarted)
        self.register(self.handle_server_stopping, ServerStopping)
        self.register(self.handle_server_stopped,  ServerStopped)

    def handle_server_event(self, event):
        webhook = WebhookObject(self.webhook_name)
        title = "Server event from: {}".format(self.server_name)
        fields = [
            {"name": "Cause", "value": event.cause},
            {"name": "Data", "value": event.data}
        ]
        webhook.add_embed(title, fields)

        self.send_webhook(webhook)
    
    def handle_server_starting(self, event):
        webhook = WebhookObject(self.webhook_name)
        title = "Server Starting Event"
        fields = []
        fields = [
            {"name": decode_if_bytes(self.server_name), "value": "Server is starting"},
            {"name": "PID", "value": event.pid},
        ]
        webhook.add_embed(title, fields)

        self.send_webhook(webhook)

    def handle_server_started(self, event):
        webhook = WebhookObject(self.webhook_name)
        title = "Server Started Event"
        fields = [
            {"name": decode_if_bytes(self.server_name), "value": "Server Started"}
        ]
        webhook.add_embed(title, fields)

        self.send_webhook(webhook)

    def handle_server_stopping(self, event):
        webhook = WebhookObject(self.webhook_name)
        title = "Server Stopping Event"
        fields = [
            {"name": decode_if_bytes(self.server_name), "value": "Server is stopping"},
            {"name": "Reason", "value": event.reason},
            {"name": "Stop Type", "value": self.stop_types.get(event.respawn)}
        ]
        webhook.add_embed(title, fields)

        self.send_webhook(webhook)
    
    def handle_server_stopped(self, event):
        webhook = WebhookObject(self.webhook_name)
        title = "Server Stopped Event"
        fields = [
            {"name": decode_if_bytes(self.server_name), "value": "Server Stopped"}
        ]
        webhook.add_embed(title, fields)

        self.send_webhook(webhook)

    def send_webhook(self, data):
        """ Sends the webhook and closes the client instance """
        _client = client.HTTPSConnection("discord.com")
        _client.request("POST", self.webhook_url, data, self.headers)
        _ = _client.getresponse()
        del _client, _
