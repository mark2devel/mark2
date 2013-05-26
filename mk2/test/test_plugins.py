from mk2 import events, plugins

import os
import sys

from twisted.internet import task
from twisted.internet.task import Clock
from twisted.trial import unittest


class TestEventDispatcher(events.EventDispatcher):
    def __init__(self):
        events.EventDispatcher.__init__(self, lambda a: None)
        self.clock = Clock()
        self.advance = self.clock.advance

    def dispatch_delayed(self, event, delay):
        return self.clock.callLater(delay, self.dispatch, event)

    def dispatch_repeating(self, event, interval, now=False):
        t = task.LoopingCall(self.dispatch, event)
        t.clock = self.clock
        t.start(interval, now)
        return t


class TestPlugin(plugins.Plugin):
    foo = 'foo'
    bar = 'bar'

    def setup(self):
        return False

    def save_state(self):
        return self.foo

    def load_state(self, state):
        self.bar = state


class PluginTestBase:
    def setUp(self):
        self.config = self
        self.fatal_error = lambda *a: None
        self.events = TestEventDispatcher()
        self.plugins = plugins.PluginManager(self, search_path='test')

    def console(self, *a, **kw):
        print a, kw

    def get_plugins(self):
        return {'test_plugins': {}}


class PluginLoading(PluginTestBase, unittest.TestCase):
    def test_load(self):
        self.assertTrue(self.plugins.load('test_plugins') is not None)

    def test_reload(self):
        self.plugins.reload('test_plugins')


class PluginTestCase(PluginTestBase, unittest.TestCase):
    def setUp(self):
        PluginTestBase.setUp(self)
        self.plugins.load('test_plugins')

    @property
    def plugin(self):
        return self.plugins['test_plugins']

    def test_load_save_state(self):
        self.assertEqual(self.plugin.foo, 'foo')
        self.assertEqual(self.plugin.bar, 'bar')
        self.plugins.reload('test_plugins')
        self.assertEqual(self.plugin.bar, 'foo')

    def test_parse_time(self):
        name, time = self.plugin.parse_time("37s")
        self.assertEqual(time, 37)

    def test_action_chain(self):
        warn = [0]
        action = [False]

        # evil
        sys.modules[plugins.Plugin.__module__].reactor = self.events.clock

        def callbackWarn(a):
            warn[0] += 1

        def callbackAction():
            action[0] = True

        act = self.plugin.action_chain("10h;10m;10s",
                                       callbackWarn,
                                       callbackAction)[1]
        act()

        for i, time in enumerate((36000, 590, 10)):
            self.assertEqual(warn[0], i + 1)
            self.events.advance(time)

        self.assertEqual(warn[0], 3)
        self.assertTrue(action[0])

    def test_action_cancel(self):
        action = [False]
        cancelled = [False]

        # evil
        sys.modules[plugins.Plugin.__module__].reactor = self.events.clock

        def callbackCancel():
            cancelled[0] = True

        def callbackAction():
            action[0] = True

        act, cancel = self.plugin.action_chain_cancellable("1s",
                                                           lambda a: None,
                                                           callbackAction,
                                                           callbackCancel)[-2:]
        act()

        self.assertFalse(action[0])
        self.assertFalse(cancelled[0])

        cancel()

        self.assertTrue(cancelled[0])

        self.events.advance(2)

        self.assertFalse(action[0])

    def test_delayed_task(self):
        calls = [0]

        def task(ev):
            calls[0] += 1

        self.plugin.delayed_task(task, 10)

        self.events.advance(9)

        self.assertEqual(calls[0], 0)

        self.events.advance(1)

        self.assertEqual(calls[0], 1)

        self.events.advance(100)

        self.assertEqual(calls[0], 1)

    def test_repeating_task(self):
        calls = [0]

        def task(ev):
            calls[0] += 1

        self.plugin.repeating_task(task, 10)

        for i in xrange(100):
            self.events.advance(10)

        self.assertEqual(calls[0], 100)

    def test_stop_tasks(self):
        calls = [0]

        def task(ev):
            calls[0] += 1

        self.plugin.repeating_task(task, 10)

        for i in xrange(100):
            self.events.advance(10)

        self.plugin.stop_tasks()

        for i in xrange(100):
            self.events.advance(10)

        self.assertEqual(calls[0], 100)
