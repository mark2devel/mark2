# mark2

[![Discord](https://img.shields.io/discord/872557175095037983?label=Join%20the%20Discord&logo=discord&style=for-the-badge)](https://discord.gg/HCvqE6TdXY)  
![GitHub last commit](https://img.shields.io/github/last-commit/gsand/mark2?label=Last%20Commit&logo=github&style=for-the-badge)

     mark2  server01  server02                                        user
    ┌────────────── server01 ──────────────┐┌─────────── stats ───────────┐
    │2015-06-04 13:55:34 | Server          ││cpu: 0.20%                   │
    │permissions file permissions.yml is   ││mem: 2.06%                   │
    │empty, ignoring it                    ││load: 0.10, 0.14, 0.11       │
    │2015-06-04 13:55:35 | Done (3.522s)!  ││players: 0 of 300            │
    │For help, type "help" or "?"          │└─────────────────────────────┘
    │2015-06-04 13:55:35 | Using epoll     │┌────────── players ──────────┐
    │channel type                          ││                             │
    │2015-06-04 13:55:35 | [NoCheatPlus]   ││                             │
    │Post-enable running...                ││                             │
    │2015-06-04 13:55:35 | [NoCheatPlus]   ││                             │
    │Post-enable finished.                 ││                             │
    │2015-06-04 13:56:16 # user attached   ││                             │
    │2015-06-04 13:56:24 # user detached   ││                             │
    │2015-06-04 14:00:37 # user attached   ││                             │
    └──────────────────────────────────────┘└─────────────────────────────┘
     >

mark2 is a minecraft server wrapper, written in python and twisted. It aims to be *the* definitive wrapper, providing a
rich feature-set and a powerful plugin interface. It has no requirement on craftbukkit.

See [INSTALL.md](INSTALL.md) for requirements and installation instructions

See [USAGE.md](USAGE.md) for details on how to use mark2

Want to contribute or are just curious how mark2 works? See the [Contribution Guide](CONTRIBUTING.md).

See the [Event Documentation](CONTRIBUTING.md#event-documentation) for details on mark2 events.

## Features

* Your server runs in the background
* Multiple users can attach at once, with their own local prompt and command buffer
* Built in monitoring using cpu, memory, players and connectivity
* Rich screen/tmux-like client with built-in monitoring, tab-complete, command history, etc

## Plugins

* Powerful scheduling plugin, with a cron-like syntax. You can hook onto events like `@serverstopped` to run a
  cartograph, or run `save` on an interval
* Automatically restart the server when it crashes, runs out of memory, or stops accepting connections
* Notifications via Prowl, Pushover, NotifyMyAndroid or email if something goes wrong.
* Relay in-game chat to IRC, and vice-versa
* MCBouncer ban support, even on a vanilla server.
* Read an RSS feed (such as a subreddit feed) and announce new entries in-game
* Back up your map and server log when the server stops
* Print a random message at an interval, e.g. '[SERVER] Lock your chests with /lock'
* Respond to user commands, e.g. '\<Notch> !teamspeak' could `msg Notch Join our teamspeak server at xyz.com`

## Compatibility

As mark2 is a port of older python 2 code, there may be some growing pains down the line for deprecations or changes that cause issues.

As of editing, mark2 was **tested and works on Python 3.11**, though it should work on Python 3.12 (just not tested atm)

If you experience **any** odd behavior (mark2 behaving improperly, not issues with your minecraft servers), feel free to [create a GitHub issue report](https://github.com/mark2devel/mark2/issues/new) on the repo here and it will be fixed as soon as possible! Thank you!
