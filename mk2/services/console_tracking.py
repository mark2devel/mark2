from mk2 import properties
from mk2.events import PlayerChat, PlayerDeath, PlayerJoin, PlayerQuit, ServerOutput
from mk2.plugins import Plugin

import re


class ConsoleTracking(Plugin):
    deaths = tuple()
    chat_events = tuple()

    def setup(self):
        lang = properties.load_jar(self.parent.jar_file, 'assets/minecraft/lang/en_US.lang', 'lang/en_US.lang')
        if lang is not None:
            self.deaths = tuple(lang.get_deaths())
            self.register(self.death_handler, ServerOutput, pattern=".*")

        self.register_chat()

    def register_chat(self):
        ev = []
        for key, e_ty in (('join', PlayerJoin),
                          ('quit', PlayerQuit),
                          ('chat', PlayerChat)):
            pattern = self.parent.config['mark2.regex.' + key]
            try:
                re.compile(pattern)
            except:
                return self.fatal_error(reason="mark2.regex.{0} isn't a valid regex!".format(key))
            ev.append(self.register(lambda e, e_ty=e_ty: self.dispatch(e_ty(**e.match.groupdict())),
                                    ServerOutput,
                                    pattern=pattern))
        self.chat_events = tuple(ev)

    def death_handler(self, event):
        for name, (pattern, format) in self.deaths:
            m = re.match(pattern, event.data)
            if m:
                self.dispatch(PlayerDeath(cause=None,
                                          format=format,
                                          **m.groupdict()))
                break
