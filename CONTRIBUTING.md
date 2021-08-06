# Contributing to mark2

First off, we'd like to thank you for helping improve mark2 and maintain it for the future of Minecraft server Admins everywhere

## Table of Contents

- [Getting Started](#getting-started)
- [Code Style](#code-style)
- [Mark2 Code Description](#mark2-code-description)
  - [Mark2 Commands](#mark2-commands)
  - [The Manager, Services and Plugins](#the-manager-services-and-plugins)
  - [Twisted Event Factories](#twisted-event-factories)
    - [User Server](#user-server)
    - [User Client](#user-client)
- [Event Documentation](#event-documentation)
  - [General Events](#general-events)
  - [Player Events](#player-events)
  - [Server Events](#server-events)
  - [Stat Events](#stat-events)
  - [User Events](#user-events)

## Getting Started

To get started you're going to need to setup an development environment to develop for mark2. The easiest way to do this would be to work on linux (since mark2 requires a UNIX-like operating system to function), but if you aren't willing to run linux on your main computer, you can install a VM or use a spare computer to run the code. The setup process is identical to that of the [install guide](INSTALL.md)

## Code Style

mark2 is not strict with code style. A small project like this that has a history of swapping maintainers can't be super picky about code style.

The only vital thing is that your code is **neat**, **efficient** and **doesn't use aspects of Python 3 not available in earlier versions**, no `f'strings'` or walrus operators (`:=`)!

mark2 aims to be backwards compatible with early versions of Python 3, roughly shooting for compatibility with Python 3.5 or later

## Mark2 Code Description

Mark2 uses Twisted's reactor system and custom events to run servers in the background and provides a detachable client.

The effect of using an event based programming system allows mark2 to reload large portions of its services and plugins without needing to restart the server process.

### Mark2 commands

All of mark2's commands are processed inside the [launcher](mk2/launcher.py). All entry points to the other parts of mark2 start there in the `main()` function located at the bottom of that file.

From there, various aspects of the code that makes up the twisted framework are setup and run.

### The Manager, Services and Plugins

When the `mark2 start` command is received, it will use the [manager](mk2/manager.py) to gather the necessary information to create and spawn a server process. The manager _manages_ the [services](mk2/services) and [plugins](mk2/plugins) that dispatch and handle a lot of the twisted events and those events make up the IO between the Server and the Clients as well as IO between plugins and services.

The difference between a plugin and a service is that services are always run as they make up the core functionality of mark2, whereas plugins can be disabled if their function is not needed.

One of those super important services, is the process service. It actually creates and spawns the java process that runs the server by listening to the `ServerStart` event generated in the manager (see `Process.server_start` where it uses the twisted reactor to spawn the server process).

Certain services cannot be reloaded without consequences, for example, the `Process` service cannot be reloaded as it would kill your minecraft server. Another example is the `User Server` service cannot be reloaded as it would detach all clients and lose the cached data that clients need when they attach (More on that in the [User Server](#user-server) section).

In the process service, it also handles all the events for the actual IO to the server process by using the `ProcessProtocol` for dispatching `ServerOutput` events for all the other aspects of mark2 and the main process services handles writing data to the server's STDIN (see `Process.server_input`)

### Twisted Event Factories

Generally, mark2's detachable client is split into two sections, the [user client](mk2/user_client.py) and the [user server](mk2/services/user_server.py).

Both contain twisted "Factories" that handle attaching and detaching from the server as well as sending user commands to the server process via the event system.

#### User Client

When the `mark2 attach` command is received, it creates an instance of `UserClientFactory` class and runs it's `main()` function. In there, it uses [urwid](https://github.com/urwid/urwid) to make a graphical user interface.

The `UserClientFactory` connects to the `UserServerFactory` socket (see `UserClientFactory.connect_to_server()`) and twisted builds a protocol using the `UserClientFactory.buildProtocol` method. This builds an instance of mark2's `UserClientProtocol` which actually handles the IO with the server factory socket.

The `UserClientProtocol` uses the `lineReceived` method to process received data and uses it's `send_helper` method to request data from the `UserServerFactory` such as the player counts, server stats and current users attached.

All the data it receives are displayed using the `UI` class.

#### User Server

The user server is an essential service to the function of mark2. It does some similar stuff to the `UserClientFactory` such as building a twisted protocol, but this time it creates the unix socket that clients can connect to.

The user server uses this socket to process requests from the `UserClientFactory` to respond with useful data it collects from various events broadcasted by the server process (console output, server stats, player counts, attached users).

It uses the `UserServerProtocol` to receive data from the client and uses it's event handlers to store data for query by the `UserClientFactory`. The `UserServerFactory` runs as long as the server is running and will cache parts of the server's state for the clients to query when they attach so they can build the UI.

## Event Documentation

**NOTE: Event documentation is still a WIP, event data is missing for now and will be added at a later date!**

A [good message](https://github.com/gsand/mark2/issues/123#issuecomment-889285837) from [edk0](https://github.com/edk0) covered some of what will be outlined here, it's suggested you read it before continuing.

Events are how plugins communicate with each other and how almost everything that happens is orchestrated.

Some of these events can be used in conjunction with the scripts plugin to execute commands (shell and minecraft!) as well as mark2 commands when a certain event is fired. Only some of these events make sense to be used with the scripts plugin. The reason events can be used in scripts is because it was a convenient. As such, scripts can technically listen to any mark2 event when they definitely should not use most of them.

To get a list of all events mark2 has, open up a server console and type `~events` in it.

Here is a brief overview of the events mark2 has to offer

### General Events

#### `Console`

Issued by the manager when the server gives output  
Used by plugins (like the user server) to handle console output from the server

#### `Error`

Unused event for a generic error

#### `Event`

Base event class used for all other events

#### `FatalError`

Issued when a fatal error causes the server process to close. Issued from the `Process` service  
Tells the manager to exit with an error message

#### `Hook`

Issued as a general purpose event to have dynamically addable events
Only used at the moment for mark2 prompt commands

### Player Events

Issued from the `ConsoleTracking` service

#### `PlayerEvent`

Base player event class used for all other player events

#### `PlayerChat`

Issued when a player sends a chat message. Triggered by chat messages in the console

#### `PlayerDeath`

Issued when a player dies. *Generally doesn't work in recent minecraft versions due to changes with the death messages*

#### `PlayerJoin`

Issued when a player connects to the server. Triggered by the `<username> logged in...` message

#### `PlayerQuit`

Issued when a player disconnects from the server. Triggered by the `<username> lost connection...` message

### Server Events

#### `ServerEvent`

Issued to inform plugins something is happening with the server
Mainly used in the push plugin to send a push notifications

#### `ServerInput`

Issued to send data to the server's stdin

#### `ServerOutput`

Issued when the server gives a line on stdout. Allows the use of a pattern to only receive lines matching the pattern

#### `ServerStart`

Issued to start the server

#### `ServerStarted`

Issued when the server has finished starting. Triggered by the `Done (123.456s)!` message and fired from the `Process` service
Typical usage of this event in the scripts is for scheduling a server restart with the `~restart` command

#### `ServerStarting`

Issued to inform plugins the server is starting

#### `ServerStop`

Issued to stop the server

#### `ServerStopping`

Issued to inform plugins the server is stopping

#### `ServerStopped`

Issued when the server stops fully

### Stat Events

#### `StatEvent`

Base stat event class used for all other stat events

#### `StatPlayerCount`

Issued by the `Ping` service to send the number of players and max number of players on a server to plugins

#### `StatPlayers`

Issued by the manager to send a list of players to plugins
Player information is gathered by the [player events](#player-events)

#### `StatProcess`

Issued by the `Process` service to inform plugins of the CPU and memory usage of the server process

### User Events

Issued from the `UserServer` service after receiving data from the `UserClient`

#### `UserAttach`

Issued to alert plugins that a user attached to the console

#### `UserDetach`

Issued to alert plugins that a user detached from the console

#### `UserInput`

Issued when a user sends a line in the prompt.
Handled by the manager to either forward the input to plugins as a [Hook](#hook) event or to dispatch a [ServerInput](#serverinput) event
