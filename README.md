# mark2 [![Build Status](https://travis-ci.org/gsand/mark2.png?branch=master)](https://travis-ci.org/gsand/mark2)

mark2 is a minecraft server wrapper, written in python and twisted. It aims to be *the* definitive wrapper, providing a
rich feature-set and a powerful plugin interface. It has no requirement on craftbukkit.

see [INSTALL.md](INSTALL.md) for requirements and installation instructions

see [USAGE.md](USAGE.md) for details on how to use mark2

## features

* Your server runs in the background
* Multiple users can attach at once, with their own local prompt and command buffer
* Built in monitoring using cpu, memory, players and connectivity
* Rich screen/tmux-like client with built-in monitoring, tab-complete, command history, etc

## plugins

* Powerful scheduling plugin, with a cron-like syntax. You can hook onto events like `@serverstopped` to run a
  cartograph, or run `save` on an interval
* Automatically restart the server when it crashes, runs out of memory, or stops accepting connections
* Notifications via Prowl, Pushover, NotifyMyAndroid or email if something goes wrong.
* Relay in-game chat to IRC, and vice-versa
* MCBouncer ban support, even on a vanilla server.
* Read an RSS feed (such as a subreddit feed) and announce new entries in-game
* Back up your map and server log when the server stops
* Print a random message at an interval, e.g. '[SERVER] Lock your chests with /lock'
* Respond to user commands, e.g. '<Notch> !teamspeak' could `msg Notch Join our teamspeak server at xyz.com`
