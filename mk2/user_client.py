import datetime
import getpass
import glob
import json
import os
import re
from string import Template

import psutil
import pyperclip
import urwid
from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory, ProcessProtocol
from twisted.internet.task import LoopingCall
from twisted.protocols.basic import LineReceiver

from . import properties
from .shared import console_repr, open_resource, decode_if_bytes, encode_if_str


class TabEvent:
    fail = None

    def __init__(self, line, players):
        pos = line.rfind(' ') + 1
        if pos == 0:
            self.left, right = "", line
        else:
            self.left, right = line[:pos], line[pos:]

        self.players = [player for player in players if re.match(right, player, re.I)]
        if len(self.players) == 0:
            self.fail = line
        self.index = 0

    def next(self):
        if self.fail:
            return self.fail
        i = self.index % len(self.players)
        self.index += 1
        return self.left + self.players[i]


class Mark2ListBox(urwid.ListBox):
    def focus_next(self):
        try: 
            self.body.set_focus(self.body.get_next(self.body.get_focus()[1])[1])
        except:
            pass

    def focus_previous(self):
        try: 
            self.body.set_focus(self.body.get_prev(self.body.get_focus()[1])[1])
        except:
            pass


class Prompt(urwid.Edit):
    def __init__(self, get_players, run_command, *a, **k):
        self.history = ['']
        self.history_pos = 0
        self.tab = None

        self.get_players = get_players
        self.run_command = run_command

        urwid.Edit.__init__(self, *a, **k)

    def get_prompt(self):
        return self.get_edit_text()

    def set_prompt(self, x):
        self.set_edit_text(x)
        self.set_edit_pos(len(x))

    def save_prompt(self):
        self.history[self.history_pos] = self.get_prompt()

    def load_prompt(self):
        self.set_prompt(self.history[self.history_pos])

    def keypress(self, size, key):
        if key != 'tab':
            self.tab = None

        if key == 'up':
            if self.history_pos > 0:
                self.save_prompt()
                self.history_pos -= 1
                self.load_prompt()
        elif key == 'down':
            if self.history_pos < len(self.history) - 1:
                self.save_prompt()
                self.history_pos += 1
                self.load_prompt()
        elif key == 'enter':
            text = self.get_prompt()
            if len(text) > 0:
                self.run_command(text)
                self.history_pos = len(self.history) - 1
                if self.history[self.history_pos - 1] == text:
                    self.set_prompt('')
                    self.cursor = 0
                    self.save_prompt()
                else:
                    self.save_prompt()
                    self.history.append('')
                    self.history_pos += 1
                    self.load_prompt()
        elif key == 'tab':
            text = self.get_prompt()
            if text == '':
                self.set_prompt('say ')
            else:
                if self.tab is None:
                    self.tab = TabEvent(text, self.get_players())
                self.set_prompt(self.tab.next())
        else:
            return urwid.Edit.keypress(self, size, key)


class PMenuButton(urwid.Button):
    def __init__(self, caption, *a):
        super().__init__(caption, *a)
        self._w = urwid.SelectableIcon(caption, 0)


class PMenuWrap(urwid.WidgetPlaceholder):
    names = ('players', 'actions', 'reasons')

    def __init__(self, actions, reasons, dispatch, escape):
        self.dispatch = dispatch
        self.escape = escape
        self._pmenu_lists   = [ (n, urwid.SimpleListWalker([])) for n    in self.names        ]
        self._pmenu_widgets = [ (n, Mark2ListBox(l))           for n, l in self._pmenu_lists ]

        self.fill(1, zip(actions, actions))
        self.fill(2, reasons)

        self.first()

        super().__init__(self._pmenu_widgets[0][1])

    def fill(self, index, items):
        name, contents = self._pmenu_lists[index]
        del contents[0:len(contents)]
        for name, result in items:
            e = urwid.AttrMap(PMenuButton(name, self.next, result), 'menu_item', 'menu_item_focus')
            contents.append(e)

    def first(self):
        self._pmenu_acc = []
        self._pmenu_stage = 0
        self.original_widget = self._pmenu_widgets[0][1]

    def next(self, widget, result):
        acc = self._pmenu_acc
        acc.append(result)
        #run command?
        if (self._pmenu_stage == 1 and (result not in ('kick', 'ban') and len(self._pmenu_lists[2][1]) > 0)) or\
           (self._pmenu_stage == 2):
            self.dispatch(' '.join([acc[1]] + [acc[0]] + acc[2:]))
            self.first()
        #next menu
        else:
            self._pmenu_stage += 1
            self.original_widget = self._pmenu_widgets[self._pmenu_stage][1]

    def prev(self):
        self._pmenu_acc.pop()
        self._pmenu_stage -= 1
        self.original_widget = self._pmenu_widgets[self._pmenu_stage][1]

    def keypress(self, size, key):
        if key == 'esc':
            if self._pmenu_stage == 0:
                self.escape()
            else:
                self.first()
        elif key == 'backspace':
            if self._pmenu_stage == 0:
                self.escape()
            else:
                self.prev()
        else:
            return self.original_widget.keypress(size, key)

    def set_players(self, players):
        content = self._pmenu_lists[0][1]
        diff = lambda a, b: [[e for e in d if e not in c] for c, d in ((a, b), (b, a))]

        add, remove = diff([b.original_widget.label for b in list(content)], players)

        #first remove players who logged off
        for b in list(content):
            if b.original_widget.label in remove:
                content.remove(b)

        #now add new players
        i = 0
        while len(add) > 0:
            a = add.pop(0)
            while i < len(content) - 1 and content[i].original_widget.label.lower() < a.lower():
                i += 1
            content.insert(i, urwid.AttrMap(PMenuButton(a, self.next, a), 'menu_item', 'menu_item_focus'))
            i += 1


class UI:
    loop = None

    def __init__(self, palette, get_players, run_command, switch_server, connect_to_server, pmenu_actions, pmenu_reasons):
        self.palette = palette
        self.get_players = get_players
        self.run_command = run_command
        self.switch_server = switch_server
        self.connect_to_server = connect_to_server

        self.pmenu_actions = pmenu_actions
        self.pmenu_reasons = pmenu_reasons

        self.lines = []
        self.filters = {}
        self.filter = lambda *a: True

        self.g_output_list = urwid.SimpleFocusListWalker([])

        self.build()

    def build(self):
        #header
        self.g_servers = urwid.Columns([])
        self.g_users   = urwid.Columns([])
        g_head         = urwid.AttrMap(urwid.Columns((('weight', 3, self.g_servers), self.g_users)), 'head')

        #main
        self.g_output      = Mark2ListBox(self.g_output_list)
        self.g_output_wrap = urwid.LineBox(urwid.AttrMap(self.g_output, 'output'))
        self.g_stats       = urwid.Text("")

        #player menu
        def escape():
            self.g_frame.focus_position='footer'
        self.g_pmenu = PMenuWrap(self.pmenu_actions, self.pmenu_reasons, self.run_command, escape)

        self.g_sidebar = urwid.Pile((
            ('pack', urwid.AttrMap(urwid.LineBox(self.g_stats, title='stats'), 'stats')),
            urwid.AttrMap(urwid.LineBox(self.g_pmenu, title="players"), 'menu')))
        self.g_main    = urwid.Columns((
            urwid.WidgetDisable(urwid.AttrMap(self.g_output_wrap, 'console')),
            ('fixed', 31, self.g_sidebar)))

        self.sidebar_visible = True

        #foot
        self.g_prompt = Prompt(self.get_players, self.run_command, ' > ')
        g_prompt = urwid.AttrMap(self.g_prompt, 'prompt', 'prompt_focus')

        self.g_frame = urwid.Frame(self.g_main, g_head, g_prompt, focus_part='footer')

        # Previous focused widgets for copy paste
        self._prev_focused = []

        #log.addObserver(lambda m: self.append_output(str(m['message'])))

    def main(self):
        self.loop = urwid.MainLoop(
            self.g_frame,
            self.palette,
            input_filter=self.filter_input,
            event_loop=urwid.TwistedEventLoop()
        )
        self.loop.run()

    def stop(self):
        def exit(*a):
            raise urwid.ExitMainLoop
        self.loop.set_alarm_in(0, exit)

    def filter_input(self, keys, raw):
        passthru = []
        for key in keys:
            if key in ('page up', 'page down', 'meta up', 'meta down'):
                # See https://stackoverflow.com/q/19446840/9873471, uniform scrolling wasn't working properly.
                if key == 'meta up':
                    self.g_output.focus_previous()
                elif key == 'meta down':
                    self.g_output.focus_next()
                else:
                    self.g_output.keypress((0, 16), key)
                self.set_focused()
            elif key == 'home':
                self.g_output.set_focus(0)
            elif key == 'end':
                self.g_output.set_focus_valign("bottom")
                self.g_output.set_focus(len(self.g_output_list) - 1, coming_from='above')
            elif key == 'meta c':
                # Copy focused widget to clipboard
                focused_text_widget, _ = self.g_output_list.get_focus()
                try:
                    pyperclip.copy(decode_if_bytes(focused_text_widget.get_text()[0]))
                except pyperclip.PyperclipException:
                    self.append_output("Cannot copy to clipboard. Is the client windows?")
            elif key == 'meta x':
                # Append focused widget to clipboard
                focused_text_widget, _ = self.g_output_list.get_focus()
                try:
                    copied_text = pyperclip.paste()
                    if copied_text is not None:
                        copied_text += "\n"
                    copied_text += decode_if_bytes(focused_text_widget.get_text()[0])
                    pyperclip.copy(copied_text)
                except pyperclip.PyperclipException:
                    self.append_output("Cannot copy to clipboard. Is the client windows?")
            elif key == 'meta left':
                self.switch_server(-1)
            elif key == 'meta right':
                self.switch_server(1)
            elif key == 'ctrl p':
                self.g_frame.focus_position = 'body'
            elif key == 'f8':
                raise urwid.ExitMainLoop
            elif key == 'f11':
                self.toggle_sidebar()
            else:
                passthru.append(key)

        return passthru

    def redraw(self):
        if self.loop:
            self.loop.draw_screen()
    
    def set_focused(self):
        """ Sets the focused widget in the terminal to a standout color and resets old standout widgets to their original formatting
        """
        focused_text, pos = self.g_output.get_focus()

        text_val = encode_if_str(focused_text.get_text()[0])
        old_attr = focused_text.get_text()[1]
        new_text = urwid.Text((urwid.AttrSpec('default,standout', 'default'), text_val))
        self.g_output_list[pos] = new_text

        for prev in self._prev_focused:
            _text_val = encode_if_str(prev[0][0].get_text()[0])
            # Attr encoded as [('attr', x), ('attr', y)] where x and y are run lengths of the attribute on the text
            _old_attr = prev[0][1] if len(prev[0][1]) > 0 else 'default'
            final_text = []
            if isinstance(_old_attr, str):
                final_text.append((_old_attr, _text_val))
            else:
                offset = 0
                # Loops over the old attributes and applies them properly for the _new_text widget
                for attr, attr_length in _old_attr:
                    # Ensure that standout lines are unset properly
                    if isinstance(attr, urwid.AttrSpec):
                        if attr.foreground == 'default,standout':
                            attr.foreground = 'default'
                    text_to_apply = _text_val[offset : attr_length + offset]
                    offset += attr_length
                    final_text.append((attr, text_to_apply))

            _pos = prev[1]
            _new_text = urwid.Text(final_text)
            self.g_output_list[_pos] = _new_text

        self._prev_focused.clear()
        self._prev_focused.append(((new_text, old_attr), pos))
        self.redraw()
        self.g_output.set_focus(pos)
    
    def toggle_sidebar(self):
        """ Toggles the visibility of the player menu and stats """
        if self.sidebar_visible:
            self.g_main.contents.pop(1)
        else:
            self.g_main.contents.append((self.g_sidebar, self.g_main.options('given', 31)))
        self.sidebar_visible = not self.sidebar_visible

    def set_servers(self, servers, current=None):
        new = []
        for s in sorted(servers):
            if s == current:
                e = urwid.AttrMap(urwid.Text((urwid.AttrSpec('default,standout', 'default'), " {} ".format(s))), 'server_current')
                self.g_output_wrap.set_title(s)
            else:
                e = urwid.AttrMap(PMenuButton(" {} ".format(s), lambda button, _s=s: self.connect_to_server(_s)), 'server')
            new.append((e, self.g_servers.options('pack')))

        contents = self.g_servers.contents
        del contents[0:len(contents)]
        contents.append((urwid.AttrMap(urwid.Text(' mark2 '), 'mark2'), self.g_servers.options('pack')))
        contents.extend(new)
        contents.append((urwid.Divider(), self.g_users.options()))

    def set_users(self, users):
        new = []
        for user, attached in users:
            e = urwid.Text(" {} ".format(user))
            e = urwid.AttrMap(e, 'user_attached' if attached else 'user')
            new.append((e, self.g_users.options('pack')))

        contents = self.g_users.contents
        del contents[0:len(contents)]
        contents.append((urwid.Divider(), self.g_users.options()))
        contents.extend(new)

    def append_output(self, line):
        # Code to allow easy appending of strings to the output of mark2 console
        if isinstance(line, str):
            line_dict = {
                'source': 'mark2',
                'data': line,
                'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            line = line_dict

        scroll = False
        del self.lines[:-999]
        self.lines.append(line)

        if not self.filter(line):
            return

        try:
            p = self.g_output.focus_position
            try:
                self.g_output.body.next_position(p)
            except IndexError:  # scrolled to end
                scroll = True
        except IndexError:  # nothing in listbox
            pass

        self.g_output_list.append(urwid.Text(colorize(line)))
        if scroll:
            self.g_output.focus_position += 1

    def set_output(self, lines=None):
        contents = self.g_output_list
        del contents[0:len(contents)]

        lines = lines or self.lines
        lines = [l for l in lines if self.filter(l)]

        for line in lines:
            contents.append(urwid.Text(colorize(line)))

        try:
            self.g_output.focus_position = len(lines) - 1
        except IndexError:  # nothing in list
            pass
        self.redraw()

    def set_filter(self, filter_):
        if isinstance(filter_, str):
            return self.set_filter(self.filters[filter_])
        self.filter = filter_.apply
        self.set_output()

    def set_players(self, players):
        self.g_pmenu.set_players(players)
        self.redraw()

    def set_stats(self, stats):
        self.g_stats.set_text(stats)
        self.redraw()


class SystemUsers(set):
    def __init__(self):
        self.me = getpass.getuser()
        set.__init__(self)

    def update_users(self):
        self.clear()
        for u in psutil.users():
            self.add(u.name)


class App:
    def __init__(self, name, interval, update, shell, command):
        self.name = name
        self.interval = interval
        self.update = update
        self.cmd = [shell, '-c', command]
        self.stopping = False
        self.start()

    def start(self):
        p = ProcessProtocol()
        self.buff     = ""
        self.protocol = p

        p.outReceived   = self.got_out
        p.processEnded  = self.got_exit
        reactor.spawnProcess(p, self.cmd[0], self.cmd)

    def got_out(self, d):
        if type(d) != str:
            d = d.decode("utf-8")
        self.buff += d

    def got_exit(self, *a):
        self.update(self.name, self.buff.strip())
        if not self.stopping:
            reactor.callLater(self.interval, self.start)


class LineFilter:
    HIDE = 1
    SHOW = 2

    def __init__(self):
        self._actions = []
        self._default = self.SHOW

    def append(self, action, *predicates):
        self.setdefault(action)
        def action_(msg):
            if all(p(msg) for p in predicates):
                return action
            return None
        self._actions.append(action_)

    def setdefault(self, action):
        if len(self._actions) == 0:
            self._default = (self.HIDE if action != self.SHOW else self.SHOW)

    def apply(self, msg):
        current = self._default
        for action in self._actions:
            current = action(msg) or current
        return current == LineFilter.SHOW


class UserClientFactory(ClientFactory):
    def __init__(self, initial_name, shared_path='/tmp/mark2'):
        self.socket_to   = lambda n: os.path.join(shared_path, n + ".sock")
        self.socket_from = lambda p: os.path.splitext(os.path.basename(p))[0]

        self.client = None
        self.stats = {}
        self.system_users = SystemUsers()

        #read the config
        self.config = properties.load(properties.ClientProperties, open_resource('resources/mark2rc.default.properties'), os.path.expanduser('~/.mark2rc.properties'))
        assert self.config is not None
        self.stats_template = Template(self.config['stats'])

        #start apps
        self.apps = []

        #start ui
        self.ui = UI(self.config.get_palette(), self.get_players, self.run_command, self.switch_server, self.connect_to_server, self.config.get_player_actions(), self.config.get_player_reasons())
        for name, command in self.config.get_apps():
            app = App(name, self.config.get_interval('apps'), self.app_update, self.config['stats.app_shell'], command)
            self.apps.append(app)

        #tasks
        t = LoopingCall(self.update_servers)
        t.start(self.config.get_interval('servers'))

        t = LoopingCall(self.update_users)
        t.start(self.config.get_interval('users'))

        t = LoopingCall(self.update_players)
        t.start(self.config.get_interval('players'))

        t = LoopingCall(self.update_stats)
        t.start(self.config.get_interval('stats'))

        self.connect_to_server(initial_name)

    def log(self, w):
        self.ui.append_output(str(w))

    def main(self):
        self.ui.main()

    def buildProtocol(self, addr):
        self.client = UserClientProtocol(self.socket_from(addr.name).decode("utf-8"), self.system_users.me, self)
        self.update_servers()
        return self.client

    def switch_server(self, delta=1):
        index = self.servers.index(self.client.name)
        self.update_servers()
        if len(self.servers) == 0:  # no running servers
            return self.ui.stop()
        if len(self.servers) == 1 and self.client.name in self.servers: 
            return # don't switch with only one server

        name = self.servers[(index + delta) % len(self.servers)]
        self.connect_to_server(name)

    def connect_to_server(self, name):
        if self.client:
            self.client.close()
        reactor.connectUNIX(self.socket_to(name), self)

    def update_servers(self):
        servers = []
        for f in glob.glob(self.socket_to('*')):
            servers.append(self.socket_from(f))

        self.servers = sorted(servers)
        self.ui.set_servers(self.servers, current=self.client.name if self.client else None)

    def update_users(self):
        self.system_users.update_users()
        if self.client:
            self.client.get_users()

    def update_players(self):
        if self.client:
            self.client.get_players()

    def update_stats(self):
        if self.client:
            self.client.get_stats()

    def app_update(self, name, data):
        self.stats[name] = data

    def get_players(self):
        if self.client:
            return self.client.players
        else:
            return []

    def run_command(self, command):
        if self.client:
            return self.client.run_command(command)

    def server_connected(self, client):
        pass

    def server_disconnected(self, client):
        self.switch_server()

    def server_output(self, line):
        self.ui.append_output(line)

    def server_scrollback(self, lines):
        self.ui.set_output(lines)

    def server_players(self, players):
        self.ui.set_players(players)

    def server_users(self, users_a):
        users_l = list(self.system_users)

        users = []
        for u in sorted(set(users_l + users_a), key=str.lower):
            users.append((u, u in users_a))

        self.ui.set_users(users)

    def server_stats(self, stats):
        self.stats.update(stats)
        self.ui.set_stats(self.stats_template.safe_substitute(self.stats))

    def server_regex(self, patterns):
        self.make_filters(patterns)

    def make_filters(self, server_patterns={}):
        cfg = {}
        cfg.update(server_patterns)
        cfg.update(self.config.get_by_prefix('pattern.'))

        # read patterns from config to get a dict of name: filter function
        def makefilter(p):
            ppp = p
            p = re.compile(p)
            def _filter(msg):
                m = p.match(msg['data'])
                return m and m.end() == len(msg['data'])
            return _filter
        patterns = {k: makefilter(p) for k, p in cfg.items()}

        patterns['all'] = lambda a: True

        # read filters
        self.ui.filters = {}
        for name, spec in self.config.get_by_prefix('filter.'):
            filter_ = LineFilter()
            action = LineFilter.SHOW
            for pattern in spec.split(','):
                pattern = pattern.strip().replace('-', '_')
                if ':' in pattern:
                    a, pattern = pattern.split(':', 1)
                    action = {'show': LineFilter.SHOW, 'hide': LineFilter.HIDE}.get(a)
                    filter_.setdefault(action)
                if not pattern:
                    continue
                filter_.append(action, patterns[pattern])
            self.ui.filters[name] = filter_
        self.ui.set_filter(self.config['use_filter'])


class NullFactory:
    def __getattr__(self, name):
        return lambda *a, **k: None


class UserClientProtocol(LineReceiver):
    MAX_LENGTH = 999999
    delimiter = b'\n'
    enabled = False

    def __init__(self, name, user, factory):
        self.name = name
        self.user = user
        self.users = set()
        self.players = list()
        self.factory = factory

    def close(self):
        self.transport.loseConnection()
        self.factory = NullFactory()

    def connectionMade(self):
        self.alive = 1
        self.send("attach", user=self.user)
        self.send("get_scrollback")
        self.factory.server_connected(self)

    def connectionLost(self, reason):
        self.alive = 0
        self.factory.server_disconnected(self)

    def lineReceived(self, line):
        #log.msg(line)
        msg = json.loads(line)
        ty = msg["type"]

        if ty == "console":    
            self.factory.server_output(msg)

        elif ty == "scrollback":
            self.factory.server_scrollback(msg['lines'])

        elif ty == "user_status":
            user = str(msg["user"])
            if msg["online"]:
                self.users.add(user)
            else:
                self.users.discard(user)
            self.factory.server_users(list(self.users))

        elif ty == "players":
            self.players = msg['players']
            self.factory.server_players(self.players)

        elif ty == "stats":
            self.factory.server_stats(msg['stats'])

        elif ty == "regex":
            self.factory.server_regex(msg['patterns'])

        else:
            self.factory.log("wat")

    def send(self, ty, **d):
        d['type'] = ty
        if self.alive:
            self.sendLine(json.dumps(d).encode("utf-8"))

    def run_command(self, command):
        if command.startswith("say"):
            command = replace_ampersand_colors(command)
        self.send("input", line=command, user=self.user)

    def get_players(self):
        self.send("get_players")

    def get_stats(self):
        self.send("get_stats")

    def get_users(self):
        self.send("get_users")


mappings_mc_ansi = {'0':30, '1':34, '2':32, '3':36, '4':31, '5':35, '6':33, '7':37,
                    '8':30, '9':34, 'a':32, 'b':36, 'c':31, 'd':35, 'e':33, 'f':37,
                    'r':0}


def safe_unicode(text):
    """
    Returns a safe unicode version of the text
    """
    if urwid.supports_unicode():
        return text
    else:
        return text.encode('ascii', errors='replace')


def replace_ampersand_colors(text):
    """
    Convert ampersand minecraft color codes to unicode section sign ones
    """
    if isinstance(text, str):
        for code in mappings_mc_ansi:
            if text.find('&' + code) != -1:
                text = text.replace('&' + code, '\u00A7' + code)
    return text


def ansi_replace(text):
    """
    Convert minecraft color codes to ansi escape codes
    """
    # First replace all ampersand colors with unicode section sign ones
    text = replace_ampersand_colors(text)
    if isinstance(text, str):
        # Replace unicode section signs with ansi colors
        if text.find('\u00A7'):
            for code in mappings_mc_ansi:
                text = text.replace('\u00A7' + code, '\033[' + str(mappings_mc_ansi[code]) + 'm')
        
        # Highlight lines with certain log level. (SEE ANSI COLOR CODES FOR WHAT EACH ONE LOOKS LIKE)
        if text.find("[WARN]") != -1:
            # Yellow
            text = text.replace("[WARN]", '\033[33m[WARN]')
        if text.find("[WARNING]") != -1:
            # Yellow
            text = text.replace("[WARNING[", '\033[33m[WARNING]')
        if text.find("[ERROR]") != -1:
            # Red
            text = text.replace("[ERROR]", '\033[31m[ERROR]')
        return text
    else:
        return text


def colorize(text):
    """
    Convert ansi escape codes to urwid display attributes
    """
    # Convert console line to something this function can use.
    text = ansi_replace(safe_unicode(console_repr(text)))

    mappings_fg = {30: 'black', 31: 'light red', 32: 'light green', 33: 'yellow', 34: 'light blue', 35: 'light magenta', 36: 'light cyan', 37: 'dark gray', 0: 'default'}
    mappings_bg = {40: 'black', 41: 'dark red', 42: 'dark green', 43: 'brown', 44: 'dark blue', 45: 'dark magenta', 46: 'dark cyan', 47: 'light gray'}

    text_attributed = []

    parts = str(text).split('\x1b')

    regex = re.compile(r"^\[([;\d]*)m(.*)$", re.UNICODE | re.DOTALL)

    for part in parts:
        r = regex.match(part)

        if r:
            if r.group(2) != '':
                foreground = 'default'
                background = 'default'
                for code in filter(None, r.group(1).split(';')):
                    if (int(code) in mappings_fg):
                        foreground = mappings_fg[int(code)]

                    if (int(code) in mappings_bg):
                        background = mappings_bg[int(code)]

                text_attributed.append((urwid.AttrSpec(foreground, background), r.group(2)))
        else:
            if part != '':
                text_attributed.append(part)

    return text_attributed


if __name__ == '__main__':
    thing = UserClientFactory('testserver')
    thing.main()
