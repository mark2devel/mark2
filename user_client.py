import getpass
import glob
import json
import os
from string import Template
from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory, ProcessProtocol
from twisted.internet.task import LoopingCall
from twisted.protocols.basic import LineReceiver
import psutil
import urwid
import properties
from shared import console_repr
from twisted.python import log


class TabEvent:
    fail = None
    def __init__(self, line, players):
        pos = line.rfind(' ')+1
        if pos == 0:
            self.left, right = "", line
        else:
            self.left, right = line[:pos], line[pos:]

        self.players = filter(lambda p: p.startswith(right), players)
        if len(self.players) == 0:
            self.fail = line
        self.index = 0

    def next(self):
        if self.fail:
            return self.fail
        i = self.index % len(self.players)
        self.index += 1
        return self.left + self.players[i]



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
            if self.history_pos < len(self.history)-1:
                self.save_prompt()
                self.history_pos += 1
                self.load_prompt()
        elif key == 'enter':
            text = self.get_prompt()
            self.run_command(text)
            self.history_pos = len(self.history) - 1
            if self.history[self.history_pos-1] == text:
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
        super(PMenuButton, self).__init__(caption, *a)
        self._w = urwid.SelectableIcon(caption, 0)

class PMenuWrap(urwid.WidgetPlaceholder):
    names = ('players', 'actions', 'reasons')
    def __init__(self, actions, reasons, dispatch, escape):
        self.dispatch = dispatch
        self.escape = escape
        self._pmenu_lists   = [ (n, urwid.SimpleListWalker([])) for n    in self.names        ]
        self._pmenu_widgets = [ (n, urwid.ListBox(l))           for n, l in self._pmenu_lists ]

        self.fill(1, zip(actions, actions))
        self.fill(2, reasons)

        self.first()

        super(PMenuWrap, self).__init__(self._pmenu_widgets[0][1])

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
        if (self._pmenu_stage == 1 and not (result in ('kick', 'ban') and len(self._pmenu_lists[2][1]) > 0)) or\
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
        diff = lambda a, b: [[e for e in d if not e in c] for c, d in ((a, b),(b, a))]

        add, remove = diff([b.original_widget.label for b in list(content)], players)

        #first remove players who logged off
        for b in list(content):
            if b.original_widget.label in remove:
                content.remove(b)

        #now add new players
        i=0
        while len(add)>0:
            a = add.pop(0)
            while i < len(content)-1 and content[i].original_widget.label.lower() < a.lower():
                i+=1
            content.insert(i, urwid.AttrMap(PMenuButton(a, self.next, a), 'menu_item', 'menu_item_focus'))
            i += 1


class UI:
    loop = None
    def __init__(self, palette, get_players, run_command, switch_server, pmenu_actions, pmenu_reasons):
        self.palette = palette
        self.get_players = get_players
        self.run_command = run_command
        self.switch_server = switch_server

        self.pmenu_actions = pmenu_actions
        self.pmenu_reasons = pmenu_reasons

        self.g_output_list   = urwid.SimpleListWalker([])

        self.build()

    def build(self):
        #header
        self.g_servers = urwid.Columns([])
        self.g_users   = urwid.Columns([])
        g_head         = urwid.AttrMap(urwid.Columns((self.g_servers, self.g_users)), 'head')

        #main
        self.g_output  = urwid.ListBox(self.g_output_list)
        self.g_stats   = urwid.Text("")

        #player menu
        def escape():
            self.g_frame.focus_position='footer'
        self.g_pmenu = PMenuWrap(self.pmenu_actions, self.pmenu_reasons, self.run_command, escape)

        g_sidebar = urwid.Pile((
            ('pack', urwid.AttrMap(urwid.LineBox(self.g_stats, title='stats'), 'stats')),
            urwid.AttrMap(urwid.LineBox(self.g_pmenu, title="players"), 'menu')))
        g_main    = urwid.Columns((
            urwid.WidgetDisable(urwid.AttrMap(urwid.LineBox(self.g_output, title='server'), 'console')),
            ('fixed', 31, g_sidebar)))

        #foot
        self.g_prompt = Prompt(self.get_players, self.run_command, ' > ')
        g_prompt = urwid.AttrMap(self.g_prompt, 'prompt', 'prompt_focus')

        self.g_frame = urwid.Frame(g_main, g_head, g_prompt, focus_part='footer')
        self.g_main = urwid.AttrMap(urwid.Padding(self.g_frame, left=1, right=1), 'frame')

        #log.addObserver(lambda m: self.append_output(str(m['message'])))

    def main(self):
        self.loop = urwid.MainLoop(
            self.g_main,
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
            if key in ('page up', 'page down'):
                self.g_output.keypress((0, 16), key)
            elif key == 'ctrl left':
                self.switch_server(-1)
            elif key == 'ctrl right':
                self.switch_server(1)
            elif key == 'ctrl p':
                self.g_frame.focus_position = 'body'
            elif key == 'f8':
                raise urwid.ExitMainLoop
            else:
                passthru.append(key)

        return passthru

    def redraw(self):
        if self.loop:
            self.loop.draw_screen()

    def set_servers(self, servers, current=None):
        new = []
        for s in sorted(servers):
            e = urwid.Text(" %s " % s)
            e = urwid.AttrMap(e, 'server_current' if s==current else 'server')
            new.append((e, self.g_servers.options('pack')))

        contents = self.g_servers.contents
        del contents[0:len(contents)]
        contents.append((urwid.AttrMap(urwid.Text(u' mark2 \u21C9 '),'mark2'), self.g_servers.options('pack')))
        contents.extend(new)
        contents.append((urwid.Divider(), self.g_users.options()))

    def set_users(self, users):
        new = []
        for user, attached in users:
            e = urwid.Text(" %s " % user)
            e = urwid.AttrMap(e, 'user_attached' if attached else 'user')
            new.append((e, self.g_users.options('pack')))

        contents = self.g_users.contents
        del contents[0:len(contents)]
        contents.append((urwid.Divider(), self.g_users.options()))
        contents.extend(new)



    def append_output(self, line):
        scroll = False
        try:
            p = self.g_output.focus_position
            try:
                self.g_output.body.next_position(p)
            except IndexError: #scrolled to end
                scroll = True
        except IndexError: #nothing in listbox
            pass

        self.g_output_list.append(urwid.Text(line))
        if scroll:
            self.g_output.focus_position += 1

        self.redraw()

    def set_output(self, lines):
        contents = self.g_output_list
        del contents[0:len(contents)]
        for line in lines:
            contents.append(urwid.Text(line))

        self.g_output.focus_position = len(lines)-1
        self.redraw()

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
        for u in psutil.get_users():
            self.add(u.name)

class App(object):
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
        self.buff += d

    def got_exit(self, *a):
        self.update(self.name, self.buff.strip())
        if not self.stopping:
            reactor.callLater(self.interval, self.start)

class UserClientFactory(ClientFactory):
    def __init__(self, initial_name, shared_path='/tmp/mark2'):
        self.socket_to   = lambda n: os.path.join(shared_path, n + ".sock")
        self.socket_from = lambda p: os.path.splitext(os.path.basename(p))[0]

        self.client = None
        self.stats = {}
        self.system_users = SystemUsers()


        #read the config
        self.config = properties.load(properties.ClientProperties, 'resources/mark2rc.default.properties', os.path.expanduser('~/.mark2rc.properties'))
        assert not self.config is None
        self.stats_template = Template(self.config['stats'])

        #start apps
        self.apps = []

        #start ui
        self.ui = UI(self.config.get_palette(), self.get_players, self.run_command, self.switch_server, self.config.get_player_actions(), self.config.get_player_reasons())
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
        self.client = UserClientProtocol(self.socket_from(addr.name), self.system_users.me, self)
        self.update_servers()
        return self.client

    def switch_server(self, delta=1):
        self.update_servers()
        if len(self.servers) == 0: #no running servers
            return self.ui.stop()
        if len(self.servers) == 1: #don't switch with only one server
            return


        index = self.servers.index(self.client.name)
        name = self.servers[(index+delta)%len(self.servers)]
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
        self.ui.append_output(console_repr(line))

    def server_scrollback(self, lines):
        self.ui.set_output([console_repr(line) for line in lines])

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



class NullFactory(object):
    def __getattr__(self, name):
        return lambda *a, **k: None

class UserClientProtocol(LineReceiver):
    MAX_LENGTH = 999999
    delimiter = '\n'
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
            if msg["online"]:
                self.users.add(msg["user"])
            else:
                self.users.discard(msg["user"])
            self.factory.server_users(list(self.users))

        elif ty == "players":
            self.players = msg['players']
            self.factory.server_players(self.players)

        elif ty == "stats":
            self.factory.server_stats(msg['stats'])

        else:
            self.factory.log("wat")

    def send(self, ty, **d):
        d['type'] = ty
        if self.alive:
            self.sendLine(json.dumps(d))

    def run_command(self, command):
        self.send("input", line=command, user=self.user)

    def get_players(self):
        self.send("get_players")

    def get_stats(self):
        self.send("get_stats")

    def get_users(self):
        self.send("get_users")
if __name__ == '__main__':
    thing = UserClientFactory('testserver')
    thing.main()


