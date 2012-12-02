# mark2

mark2 is a minecraft server wrapper, written in python and twisted. It aims to
be *the* definitive wrapper, providing a rich feature-set and a powerful 
plugin interface. It has no requirement on craftbukkit.

## features

* Your server runs in the background
* Multiple users can attach at once, with their own local prompt and command 
  buffer
* Built in monitoring using the [snooper](wiki.vg/Session#Snoop), 
  [query](wiki.vg/Query), and [ping](wiki.vg/Server_List_Ping)
* Tab-complete player names

## features provided by plugins

* Powerful scheduling plugin, with a cron-like syntax. You can hook onto 
  events like `server shutdown` to run an external script, or run `save` on an
  interval
* Automatically restart the server when it crashes, runs out of memory, or
  stops accepting connections
* Relay in-game chat to IRC, and vice-versa
* MCBouncer ban support, even on a vanilla server.
* With [bukkit-sudo](https://github.com/edk141/bukkit-sudo), attribute certain
  commands to your in-game username, such that `ban Notch` won't be issued by 
  'console'
* Read an RSS feed (such as a subreddit feed) and announce new entries in-game
* Back up your map and server log when the server stops
* Print a random message at an interval, e.g. '[SERVER] Lock your chests with 
  /lock'
* Respond to user commands, e.g. '<Notch> !teamspeak' could `msg Notch Join 
  our teamspeak server at xyz.com`

## requirements

* UNIX-like operating system (Linux, Mac OS X, BSD)
* Python 2
* twisted
* twisted-web
* twisted-words (for IRC support)
* blessings
* clize

On ubuntu/debian:

    # apt-get install python-twisted python-twisted-web python-twisted-words
    $ pip install blessings clize

## installation

    $ git clone git@github.com:mcdevs/mark2.git
    # ln -s /path/to/mark2/mark2 /usr/bin/mark2

Essentially you just need to make sure the 'mark2' executable is in your path.

## configuration

On first start, mark2 will prompt you to edit the global config file, located 
at `config/mark2.properties`. 

To set up a server with a different config, create a `mark2.properties` file
in the same directory as the server jar. mark2 will look for config values in
this file first, and will check the global config if it can't find the key.

The following plugins also require config files in the server directory:

* script: `scripts.txt`: scriptable event handlers and recurring tasks
* alert: `alerts.txt`: e.g. "Lock your chests with /lock! ..."
* trigger: `triggers.txt`: e.g. "!teamspeak:Join our teamspeak server at xyz"

There are examples of these in the `samples/` directory

## start

To start a minecraft server:

    $ mark2 start /path/to/servers/server-name

If you're already in the right directory, you can omit the last parameter.

mark2 now refers to your server by the name of the directory containing the
server jar, in this case 'server-name'

## attach

To attach to a wrapped server:

    $ mark2 attach server-name

Swap out 'server-name' for whatever your server is actually called, for
example 'pvp' or 'creative'.

If you omit the 'name' parameter, you'll just attach to the first server 
alphabetically. If you only run one server, you may as well omit this param.

### controls

* You can navigate text with the left and right arrow keys, and home/end keys
* Use command scrollback with the up and down arrow keys
* Press tab to auto-complete a player name, or write 'say ' if you haven't
  entered any text
* Switch between servers with ctrl + left/right arrow key.
* Switch in and out of monitor mode with ctrl + up/down arrow key.

Run `~commands` to see what mark2 commands are available.

If you prefix a line with `#`, it acts as a comment that isn't interpretted.
This is handy for talking to other attached admins.

## send commands

You can send commands to the server from the command line, for example:

    $ mark2 send server-name kick Notch

## stopping/restarting

mark2 provides a few aliases here, equivilent to running, for example, 
`mark2 send server-name ~kill`

    $ mark2 stop server-name
    $ mark2 kill server-name
    $ mark2 restart server-name
    $ mark2 restart-kill server-name

'stop' and 'restart' will attempt to gracefully shut down the server, and will
kill it after a configurable timeout.

## tips

If your server has a strange name, you have a couple of options:

1. add it to `mark2.jar_path` in your mark2.properties
2. specify the full path to the jar in `mark2 start`

If your servers all reside in one directory, you may want to add a start
helper to your path:

    #!/bin/bash
    mark2 start /path/to/servers/$1

And run it like
    
    $ mcstart pvp

Likewise if `mark2 attach` becomes a little too much, you could always 
`alias at='mark2 attach'`
