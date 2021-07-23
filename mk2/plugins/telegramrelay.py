import re
import os.path as path

from telegram.ext import Updater
from telegram.ext import MessageHandler, Filters, BaseFilter
import logging

from mk2.plugins import Plugin
from mk2.events import PlayerChat, PlayerJoin, PlayerQuit, PlayerDeath, ServerOutput, ServerStopping, ServerStarting, StatPlayers, Hook

class channelFilter(BaseFilter):
    telegram_channel = None
    def __init__(self, telegram_channel):
        self.telegram_channel = telegram_channel

    def filter(self,message):
        return self.telegram_channel==message.chat_id

class TelegramBot:
    """docstring for TelegramBot."""
    telegram_channel = None
    mainchannelFilter = None
    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin
        self.updater = Updater(token=plugin.telegram_token)
        self.dispatcher = self.updater.dispatcher
        self.telegram_channel = plugin.telegram_channel
        self.mainchannelFilter = channelFilter(self.telegram_channel)

    def relay(self,message):
        self.updater.bot.sendMessage(chat_id=self.telegram_channel, text=message)

    def handleTelegramMessage(self,bot,update):
        self.plugin.telegram_message(update.message.from_user.username,update.message.text)

    def start(self):
        mark2_handler = MessageHandler(Filters.text&self.mainchannelFilter, self.handleTelegramMessage)
        self.dispatcher.add_handler(mark2_handler)

        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)
        self.updater.start_polling()
        print("Bot starting")

    def stop(self):
        self.updater.stop()
        print("Bot stopping")


class TelegramRelay(Plugin):
    #connection
    telegram_token              = Plugin.Property(required=True)
    telegram_channel            = Plugin.Property(required=True)
    #game -> irc settings
    game_columns = Plugin.Property(default=True)

    game_status_enabled = Plugin.Property(default=True)
    game_status_format  = Plugin.Property(default="!, | server {what}.")

    game_chat_enabled = Plugin.Property(default=True)
    game_chat_format  = Plugin.Property(default="{username}, | {message}")
    game_chat_private = Plugin.Property(default=None)

    game_join_enabled = Plugin.Property(default=True)
    game_join_format  = Plugin.Property(default="*, | --> {username}")

    game_quit_enabled = Plugin.Property(default=True)
    game_quit_format  = Plugin.Property(default="*, | <-- {username}")

    game_death_enabled = Plugin.Property(default=True)
    game_death_format  = Plugin.Property(default="*, | {text}")

    game_server_message_enabled = Plugin.Property(default=True)
    game_server_message_format  = Plugin.Property(default="#server, | {message}")

    #bukkit only
    game_me_enabled = Plugin.Property(default=True)
    game_me_format  = Plugin.Property(default="*, | {username} {message}")

    #irc -> game settings
    telegram_chat_enabled    = Plugin.Property(default=True)
    telegram_chat_command    = Plugin.Property(default="say [TELEGRAM] <{nickname}> {message}")
    telegram_action_command  = Plugin.Property(default="say [TELEGRAM] * {nickname} {message}")
    telegram_chat_status     = Plugin.Property(default=None)

    telegram_command_prefix  = Plugin.Property(default="!")
    telegram_command_status  = Plugin.Property(default=None)
    telegram_command_allow   = Plugin.Property(default="")
    telegram_command_mark2   = Plugin.Property(default=False)

    telegram_players_enabled = Plugin.Property(default=True)
    telegram_players_format  = Plugin.Property(default="*, | players currently in game: {players}")

    def setup(self):
        self.players = []
        self.bot = TelegramBot(self)
        self.bot.start()
        if self.game_status_enabled:
            self.register(self.handle_stopping, ServerStopping)
            self.register(self.handle_starting,  ServerStarting)

        self.column_width = 16
        self.register(self.restart_listener, Hook, public=True, name='telegramRestart', doc='Restart the listener')

        def register(event_type, format, filter_=None, *a, **k):
            def handler(event, format):
                d = event.match.groupdict() if hasattr(event, 'match') else event.serialize()
                if filter_ and 'message' in d:
                    if filter_.match(d['message']):
                        return
                line = self.format(format, **d)
                self.bot.relay(line)
            self.register(lambda e: handler(e, format), event_type, *a, **k)

        if self.game_chat_enabled:
            if self.game_chat_private:
                try:
                    filter_ = re.compile(self.game_chat_private)
                    register(PlayerChat, self.game_chat_format, filter_=filter_)
                except:
                    self.console("plugin.telegram.game_chat_private must be a valid regex")
                    register(PlayerChat, self.game_chat_format)
            else:
                register(PlayerChat, self.game_chat_format)

        if self.game_join_enabled:
            register(PlayerJoin, self.game_join_format)

        if self.game_quit_enabled:
            register(PlayerQuit, self.game_quit_format)

        if self.game_death_enabled:
            def handler(event):
                d = event.serialize()
                for k in 'username', 'killer':
                    if k in d and d[k] and d[k] in self.factory.client.users:
                        d[k] = self.mangle_username(d[k])
                text = event.get_text(**d)
                line = self.format(self.game_death_format, text=text)
                self.bot.relay(line)
            self.register(handler, PlayerDeath)

        if self.game_server_message_enabled and not (self.telegram_chat_enabled and self.telegram_chat_command.startswith('say ')):
            register(ServerOutput, self.game_server_message_format, pattern=r'\[(?:Server|SERVER)\] (?P<message>.+)')

        if self.game_me_enabled:
            register(ServerOutput, self.game_me_format, pattern=r'\* (?P<username>[A-Za-z0-9_]{1,16}) (?P<message>.+)')

        if self.telegram_chat_enabled:
            self.register(self.handle_players, StatPlayers)

    def teardown(self):
        self.bot.stop()

    def mangle_username(self, username):
        return username

    def format(self, format, **data):
        if self.game_columns:
            f = str(format).split(',', 1)
            f[0] = f[0].format(**data)
            if len(f) == 2:
                f[0] = f[0].rjust(self.column_width)
                f[1] = f[1].format(**data)
            return ''.join(f)
        else:
            return format.format(**data)

    def handle_starting(self, event):
        self.bot.relay(self.format(self.game_status_format, what="starting"))
        self.bot.start()

    def handle_stopping(self, event):
        self.bot.relay(self.format(self.game_status_format, what="stopping"))
        self.bot.stop()

    def handle_players(self, event):
        self.players = sorted(event.players)

    def telegram_message(self, user, message):
        if self.telegram_chat_enabled:
            self.send_format(self.telegram_chat_command, nickname=user, message=message)

    def restart_listener(self,event):
        self.bot.stop()
        self.bot.start()
        print("Bot Restarted")
