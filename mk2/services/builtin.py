from mk2 import events, properties
from mk2.services import process
from mk2.shared import find_config, open_resource
from mk2.plugins import Plugin

import os


class Builtin(Plugin):
    def setup(self):
        self.register(self.handle_cmd_help,          events.Hook, public=True, name="help", doc="displays this message")
        self.register(self.handle_cmd_events,        events.Hook, public=True, name="events", doc="lists events")
        self.register(self.handle_cmd_plugins,       events.Hook, public=True, name="plugins", doc="lists running plugins")
        self.register(self.handle_cmd_reload_plugin, events.Hook, public=True, name="reload-plugin", doc="reload a plugin")
        self.register(self.handle_cmd_rehash,        events.Hook, public=True, name="rehash", doc="reload config and any plugins that changed")
        self.register(self.handle_cmd_reload,        events.Hook, public=True, name="reload", doc="reload config and all plugins")
        self.register(self.handle_cmd_jar,           events.Hook, public=True, name="jar", doc="wrap a different server jar")
    
    def table(self, v):
        m = 0
        for name, doc in v:
            m = max(m, len(name))
        
        for name, doc in sorted(v, key=lambda x: x[0]):
            self.console(" ~%s | %s" % (name.ljust(m), doc))

    def handle_cmd_help(self, event):
        o = []
        for _, callback, args in self.parent.events.get(events.Hook):
            if args.get('public', False):
                o.append((args['name'], args.get('doc', '')))
        
        self.console("The following commands are available:")
        self.console("A \".\" can be used instead of \"~\".")
        self.table(o)
    
    def handle_cmd_events(self, event):
        self.console("The following events are available:")
        self.table([(n, c.doc) for n, c in events.get_all()])

    def handle_cmd_plugins(self, events):
        self.console("These plugins are running: " + ", ".join(sorted(self.parent.plugins.keys())))

    def handle_cmd_reload_plugin(self, event):
        if event.args in self.parent.plugins:
            self.parent.plugins.reload(event.args)
            self.console("%s reloaded." % event.args)
        else:
            self.console("unknown plugin.")

    def handle_cmd_rehash(self, event):
        # make a dict of old and new plugin list
        plugins_old = dict(self.parent.config.get_plugins())
        self.parent.load_config()
        plugins_new = dict(self.parent.config.get_plugins())
        # reload the union of old plugins and new plugins
        requires_reload = set(plugins_old.keys()) | set(plugins_new.keys())
        # (except plugins whose config is exactly the same)
        for k in list(requires_reload):
            if plugins_old.get(k, False) == plugins_new.get(k, False):
                requires_reload.remove(k)
        requires_reload = list(requires_reload)
        # actually reload
        for p in requires_reload:
            self.parent.plugins.reload(p)
        reloaded = filter(None, requires_reload)
        self.console("%d plugins reloaded: %s" % (len(reloaded), ", ".join(reloaded)))

    def handle_cmd_reload(self, event):
        self.parent.plugins.unload_all()
        self.parent.load_config()
        self.parent.load_plugins()
        self.console("config + plugins reloaded.")

    def handle_cmd_jar(self, event):
        new_jar = process.find_jar(
            self.parent.config['mark2.jar_path'].split(';'),
            event.args)
        if new_jar:
            self.console("I will switch to {0} at the next restart".format(new_jar))
            self.parent.jar_file = new_jar
        else:
            self.console("Can't find a matching jar file.")
