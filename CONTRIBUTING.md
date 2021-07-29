# Contributing to mark2

First off, we'd like to thank you for helping improve mark2 and maintain it for the future of Minecraft server Admins everywhere

## Table of Contents

- [Getting Started](#getting-started)
- [Code Style](#code-style)
- [Mark2 Code Description](#mark2-code-description)
  - [Mark2 Commands](#mark2-commands)
  - [The manager](#the-manager)
  - [Twisted Event Factories](#twisted-event-factories)
    - [User Server](#user-server)
    - [User Client](#user-client)
- [Event Documentation](#event-documentation)

## Getting Started

To get started you're going to need to setup an development environment to develop for mark2. The easiest way to do this would be to work on linux (since mark2 requires a UNIX-like operating system to function), but if you aren't willing to run linux on your main computer, you can install a VM or use a spare computer to run the code. The setup process is identical to that of the [install guide](INSTALL.md)

## Code Style

mark2 is not strict with code style. A small project like this that has a history of swapping maintainers can't be super picky about code style.

The only vital thing is that your code is **neat**, **efficient** and **doesn't use aspects of Python 3 not available in earlier versions**, no `f'strings'` or walrus operators (`:=`)!

mark2 aims to be backwards compatible with early versions of Python 3, roughly shooting for compatibility with Python 3.5 or later

## Mark2 Code Description

Mark2 uses Twisted's reactor system and custom events to run servers in the background and provides a detachable client.

### Mark2 commands

All of mark2's commands are processed inside the [launcher](mk2/launcher.py). All entry points to the other parts of mark2 start there in the `main()` function located at the bottom of that file.

From there, various aspects of the code that makes up the twisted framework are setup and run.

### The Manager

When the `mark2 start` command is received, it will use the [manager](mk2/manager.py) to gather the necessary information to create and spawn a process. The manager _manages_ and dispatches a lot of the twisted events and therefore the IO between the Server and the Clients.

It generates all important events listened to by [services](mk2/services) and [plugins](mk2/plugins) and is kind of the go-between for most stuff in mark2.

One of those super important services, is the process service. It actually creates and spawns the java process that runs the server by listening to the `ServerStart` event generated in the manager (see `Process.server_start` where it uses the twisted reactor to spawn the server process).

In the process service, it also handles all the events for the actual IO to the server process by using the `ProcessProtocol` for dispatching `ServerOutput` events for all the other aspects of mark2 and the main process services handles writing data to the server's STDIN (see `Process.server_input`)

### Twisted Event Factories

Generally, mark2 is split into two sections, the [user client](mk2/user_client.py) and the [user server](mk2/services/user_server.py).

Both contain twisted "Factories" that handle attaching and detaching from server the process.

#### User Client

When the `mark2 attach` command is received, it creates an instance of `UserClientFactory` class and runs it's `main()` function. In there, it uses [urwid](https://github.com/urwid/urwid) to make a graphical user interface.

The `UserClientFactory` connects to the `UserServerFactory` socket (see `UserClientFactory.connect_to_server()`) and twisted builds a protocol using the `UserClientFactory.buildProtocol` method. This builds an instance of mark2's `UserClientProtocol` which actually handles the IO with the server factory socket.

The `UserClientProtocol` uses the `lineReceived` method to process received data and uses it's `send_helper` method to request data from the `UserServerFactory` such as the player counts, server stats and current users attached.

All the data it receives are displayed using the `UI` class.

#### User Server

Once all the event dispatchers are firing, the `UserServerFactory` comes into play.

It does some similar stuff to the `UserClientFactory` where it builds a protocol, but this time it creates the unix socket that clients can listen to.

The user server uses this socket to process requests from the `UserClientFactory` to respond with useful data it collects from various events broadcasted by the server process (console output, server stats, player counts, attached users).

It uses the `UserServerProtocol` to receive data and stores it for query by the `UserClientFactory` as well as handles attaching/detaching users to the server and will provide them all the data they need to see when attaching.

## Event Documentation

### WIP
