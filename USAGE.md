# usage

## config

On first start, mark2 will prompt you to edit the global config file, located at `config/mark2.properties`.

To set up a server with a different config, create a `mark2.properties` file in the same directory as the server jar.
mark2 will look for config values in this file first, and will check the global config if it can't find the key.

The following plugins also require config files in the server directory:

* script: `scripts.txt`: scriptable event handlers and recurring tasks
* alert: `alerts.txt`: e.g. "Lock your chests with /lock! ..."
* trigger: `triggers.txt`: e.g. "!teamspeak,Join our teamspeak server at xyz"

There are examples of these in the `samples/` directory

## start

To start a minecraft server:

    mark2 start /path/to/servers/server-name

If you're already in the right directory, you can omit the path.

mark2 now refers to your server by the name of the directory containing the server jar, in this case 'server-name'

If you're on a multi-user system, you'll need to create a dedicated user for running your servers. See INSTALL for
details.

## attach

To attach to a wrapped server:

    mark2 attach -n server-name

Swap out 'server-name' for whatever your server is actually called, for example 'pvp' or 'creative'.

If you omit the 'name' parameter, you'll just attach to the first server alphabetically. If you only run one server, you
may as well omit this param.

Much of the client is configurable. See `resources/mark2rc.default.properties` for the default settings, and drop a file
called `.mark2rc.properties` in your home directory to customize.

### controls

* Use command scrollback with the up and down arrow keys
* Scroll with pageup, pagedown, alt/option + up, alt/option + down, home, and end
* Copy selected line with alt/option + c or add append selected line with alt/option + x
* Press tab to auto-complete a player name, or write 'say ' if you haven't entered any text
* Switch between servers with alt/option + left/right arrow key.
* Switch to the players list with ctrl + p
* Move back a menu level with backspace, or move straight to the first with esc
* Press either esc or backspace while on the player menu to focus the prompt
* Press f8 or ctrl-c to exit

Run `~help` to see what mark2 commands are available.

If you prefix a line with `#`, it acts as a comment that isn't interpretted. This is handy for talking to other attached
admins.

## send commands

You can send commands to the server from the command line, for example:

    mark2 send -n server-name kick Notch

## stopping/restarting

    mark2 stop -n server-name
    mark2 kill -n server-name

`stop` will attempt to gracefully shut down the server, and will kill it after a configurable timeout.
