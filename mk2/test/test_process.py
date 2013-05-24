from mk2 import events
from mk2.services import process

import random

from twisted.internet import error
from twisted.python.failure import Failure

from twisted.trial import unittest


class ProcessProtocolTestCase(unittest.TestCase):
    def setUp(self):
        self.dispatched = []
        self.proto = process.ProcessProtocol(self.dispatch, 'utf8')

    def dispatch(self, event):
        self.dispatched.append(event)

    def test_output(self):
        random.seed()

        data = '''a line of output
and another line of output
this line is incomplete'''

        lines = data.split('\n')

        while data:
            index = random.randint(1, min(len(data), 18))
            bit, data = data[:index], data[index:]
            self.proto.childDataReceived(1, bit)

        self.assertTrue(self.dispatched)

        while self.dispatched:
            event = self.dispatched.pop(0)
            self.assertIsInstance(event, events.ServerOutput)
            self.assertEqual(event['data'], lines.pop(0))

        self.assertEqual(len(lines), 1)  # the data after the final \n

    def test_process_success(self):
        fail = Failure(error.ProcessDone(None))

        self.proto.processEnded(fail)

        self.assertFalse(self.proto.alive)

        self.assertEqual(len(self.dispatched), 1)
        self.assertIsInstance(self.dispatched[0], events.ServerStopped)

    def test_process_failure(self):
        fail = Failure(error.ProcessTerminated(exitCode=1))

        self.proto.processEnded(fail)

        self.assertFalse(self.proto.alive)

        self.assertTrue(any(isinstance(event, events.FatalError) for event in self.dispatched))
