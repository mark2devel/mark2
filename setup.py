from setuptools import setup

from setuptools.command.install import install
import os
import sys

MARK2_VERSION = "2.0"

requirements = ["{0}=={1}".format(*s) for s in [

("feedparser", "6.0.8"),
("psutil",     "5.8.0"),
("pyOpenSSL",  "20.0.1"),
("Twisted",    "21.2.0"),
("urwid",      "2.1.2"),

] if "MARK2_NO_{0}".format(s[0].upper()) not in os.environ]


# helper to get round distutils' lack of support for data directories
def everything(path):
    ls = []
    path = os.path.join(os.path.dirname(__file__), path)
    for dirpath, dirnames, filenames in os.walk(path):
        ls.extend(os.path.join(dirpath, fn) for fn in filenames)
    return ls


# custom install command to let us run our own installer afterwards
class mark2install(install):
    def check_config(self):
        if "VIRTUAL_ENV" in os.environ:
            cd = os.path.join(os.environ["VIRTUAL_ENV"], ".config", "mark2")
        elif os.getuid() == 0:
            cd = os.path.join("/etc", "mark2")
        else:
            cd = os.path.join(os.path.expanduser("~"), ".config", "mark2")

        if not os.path.exists(cd):
            os.makedirs(cd)

    def run(self):
        install.run(self)
        
        self.check_config()


# setuptools uses an insane hack involving sys._getframe to make sure
# install.run() is called by the right thing.
_getframe = sys._getframe

def getframe(depth=0):
    depth += 1  # we're a frame
    i = 0
    while i <= depth:
        frame = _getframe(i)
        if frame.f_code == mark2install.run.__code__:
            depth += 1
        i += 1
    return frame

sys._getframe = getframe


setup(
    name="mark2",
    version=MARK2_VERSION,

    packages=[
        'mk2',
        'mk2.events',
        'mk2.plugins',
        'mk2.servers',
        'mk2.services',
        'mk2.test'
    ],

    package_data={
        'mk2': ['resources/*.properties'],
    },

    entry_points={
        'console_scripts': [
            'mark2 = mk2.launcher:main'
        ]
    },

    cmdclass={
        'install': mark2install
    },

    install_requires=requirements,

    zip_safe=True,

    author="Barnaby Gale & Ed Kellett",
    author_email="not.real.email@mark2.io",
    description="Minecraft server wrapper",
    license="MIT",
    keywords="mark2 minecraft server wrapper",
    url="http://mark2.io/",

    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Framework :: Twisted",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: POSIX",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 2 :: Only",
        "Topic :: Utilities"
    ],

    long_description='''
===================
mark2 |buildstatus|
===================

mark2 is a minecraft server wrapper, written in python and twisted. It aims to
be *the* definitive wrapper, providing a rich feature-set and a powerful plugin
interface. It has no requirement on craftbukkit.

features
--------

* Your server runs in the background
* Multiple users can attach at once, with their own local prompt and command
  buffer
* Built in monitoring using cpu, memory, players and connectivity
* Rich screen/tmux-like client with built-in monitoring, tab-complete, command
  history, etc

plugins
-------

* Powerful scheduling plugin, with a cron-like syntax. You can hook onto events
  like ``@serverstopped`` to run a
  cartograph, or run ``save`` on an interval
* Automatically restart the server when it crashes, runs out of memory, or
  stops accepting connections
* Notifications via Prowl, Pushover, NotifyMyAndroid or email if something goes
  wrong.
* Relay in-game chat to IRC, and vice-versa
* MCBouncer ban support, even on a vanilla server.
* Read an RSS feed (such as a subreddit feed) and announce new entries in-game
* Back up your map and server log when the server stops
* Print a random message at an interval, e.g. '[SERVER] Lock your chests with
  /lock'
* Respond to user commands, e.g. '<Notch> !teamspeak' could `msg Notch Join our
  teamspeak server at example.com`

.. |buildstatus| image:: https://travis-ci.org/mcdevs/mark2.png?branch=master
'''
)
