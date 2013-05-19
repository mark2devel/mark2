from .. import events
from ..events import Event, EventPriority

from twisted.trial import unittest


class TestEvent(Event):
    name = Event.Arg()

    def prefilter(self, name=None):
        return self.name == name


class EventWithArgs(Event):
    required = Event.Arg(required=True)
    default = Event.Arg(default='foo')


class PrefilterTest_1(Event):
    def prefilter(self, require, optional=None):
        pass


class PrefilterTest_2(Event):
    def prefilter(self, require, optional=None, **excess):
        pass


class EventsTestCase(unittest.TestCase):
    def setUp(self):
        self.events = events.EventDispatcher(lambda *a: None)

    @staticmethod
    def eating_handler(event):
        return Event.EAT

    @staticmethod
    def unregistering_handler(event):
        return Event.UNREGISTER

    def test_dispatch(self):
        """
        Test basic event dispatching.
        """
        self.hit = False

        def handler(event):
            self.hit = True

        self.events.register(handler, TestEvent)
        
        self.events.dispatch(TestEvent())

        self.assertTrue(self.hit)

    def test_priority(self):
        """
        Test event priority ordering.
        """
        self.hit_1, self.hit_2 = False, False

        def handler_1(event):
            self.hit_1 = True

        def handler_2(event):
            self.hit_2 = self.hit_1

        self.events.register(handler_1, TestEvent, priority=EventPriority.HIGH)
        self.events.register(handler_2, TestEvent, priority=EventPriority.LOW)

        self.events.dispatch(TestEvent())

        self.assertTrue(self.hit_2)

    def test_priority_decorator(self):
        """
        Test event priority decorators (like @EventPriority.HIGH)
        """
        self.hit_1, self.hit_2 = False, False

        @EventPriority.HIGH
        def handler_1(event):
            self.hit_1 = True

        @EventPriority.LOW
        def handler_2(event):
            self.hit_2 = self.hit_1

        self.events.register(handler_1, TestEvent)
        self.events.register(handler_2, TestEvent)

        self.events.dispatch(TestEvent())

        self.assertTrue(self.hit_2)

    def test_eat(self):
        """
        Test Event.EAT
        """
        self.hit = False

        def handler(event):
            self.hit = True

        self.events.register(self.eating_handler, TestEvent, priority=EventPriority.HIGH)
        self.events.register(handler, TestEvent, priority=EventPriority.LOW)

        self.events.dispatch(TestEvent())

        self.assertFalse(self.hit)

    def test_unregister(self):
        """
        Test unregistering events.
        """
        id_ = self.events.register(lambda event: None, TestEvent)

        # it should be handled now
        handled = self.events.dispatch(TestEvent())
        self.assertTrue(self.successResultOf(handled))

        # but not once we unregister it
        self.events.unregister(id_)
        handled = self.events.dispatch(TestEvent())
        self.assertFalse(self.successResultOf(handled))

    def test_unregister_from_event(self):
        """
        Test Event.UNREGISTER
        """
        self.events.register(self.unregistering_handler, TestEvent)

        handled = self.events.dispatch(TestEvent())
        self.assertTrue(self.successResultOf(handled))

        handled = self.events.dispatch(TestEvent())
        self.assertFalse(self.successResultOf(handled))

    def test_event_args(self):
        """
        Test Event.Arg
        """
        self.assertRaises(Exception, EventWithArgs)
        ev = EventWithArgs(required=True)
        self.assertEqual(ev.default, 'foo')

    def test_prefilter_check(self):
        """
        Test Event.prefilter() arg checking
        """
        def handler(event):
            pass

        self.assertRaises(Exception, self.events.register, handler, PrefilterTest_1)
        self.assertRaises(Exception, self.events.register, handler, PrefilterTest_2)

        self.events.register(handler, PrefilterTest_1, require='foo')
        self.events.register(handler, PrefilterTest_2, require='foo')

        self.events.register(handler, PrefilterTest_1, require='foo', optional='bar')
        self.events.register(handler, PrefilterTest_2, require='foo', optional='bar')

        self.assertRaises(Exception, self.events.register, handler, PrefilterTest_1,
                          require='foo', optional='bar', fooarg='excess argument')
        self.events.register(handler, PrefilterTest_2,
                             require='foo', optional='bar', fooarg='excess argument')
