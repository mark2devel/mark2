# Installation

## Note

If you are updating from the Python 2 version of mark2, please ensure you install the dependencies in your Python 3 site-packages. Failure to do so will result in errors.

## Pre-Requirements

* A UNIX-like server operating system (Linux, Mac OS X, BSD)
* Python 3+
* X11Forwarding configuration for server and client (Native on UNIX clients, windows clients require additional installation steps!)

## Installing mark2

mark2 doesn't need to be installed to a particular directory, but if you have no reasonable ideas `/usr/mark2` will be
okay. First, download mark2:

    git clone https://github.com/gsand/mark2.git

If you don't have git (and you probably should!) you could:

    wget https://github.com/gsand/mark2/archive/master.tar.gz
    tar zxvf master.tar.gz
    rm master.tar.gz
    mv mark2-master mark2

Next, symlink the `mark2` script into your executable path:

    sudo ln -s /usr/mark2/mark2 /usr/bin/mark2

## Installing mark2 requirements

Once mark2 is installed, you will need to install the python packages it uses. All commands are operating under the assumption you are in the same directory you cloned/downloaded mark2 into (`/usr/mark2` in the above example).

### Debian/Ubuntu

    sudo apt-get install python3-pip xclip
    sudo pip3 install -r requirements.txt

### Arch

    sudo pacman -S --needed python python-psutil python-urwid python-twisted python-service-identity python-feedparser python-pyopenssl xclip

The `--needed` flag will skip packages already installed.

### CentOS

CentOS requires adding a new yum repository for the installation of `xclip`

    sudo yum install epel-release.noarch
    sudo yum install python3-pip xclip
    sudo pip3 install -r requirements.txt

## Configuring Windows Clients

On Windows, there are additional steps needed before you can use the copy and paste feature of mark2. The following guide assumes you are using default PuTTY to ssh into the server running mark2.

1. Open PuTTY and navigate to the `Connection > SSH > X11` section and check `Enable X11 Forwarding`
2. Go back to `Session` and click `Default Settings` and click `Save`

Once that's complete, you will need to install an X-Server to run under windows to allow X11 forwarding to work.

The recommended X-Server for windows is [VcXsrv](https://sourceforge.net/projects/vcxsrv/).

1. Download it, run the installer. Make sure to allow it to create a desktop shortcut so you can run it easily.
2. Once installed, run the XLaunch shortcut on your desktop.
3. All settings for mark2 should be checked by default, go through to set it up how you want, but make sure you at least have `Clipboard` and all its options checked.
4. Once done, just click finish and it should launch the X-Server (Icon will appear on your tray)

Testing the X-Server install worked

1. Connect to the UNIX Server running mark2
2. Type in the console `echo 'testing123' | xclip -i` and then try to paste somewhere on the windows client, you should see `testing123` was copied to your clipboard.

Now whenever you want to use mark2's copy feature, just run the VcXsvr shortcut on your desktop and then connect to the UNIX server running mark2

## Tips

### Multiple system users running servers

If you run mark2 on a server where you expect multiple system users to start servers, you *need* to create a dedicated
user to run servers under.

    sudo adduser mcservers

To start a server, run `mark2 start` as `sudo -u mcservers mark2 start ...`

### Strange server names

If your server has a strange name, you have a couple of options:

1. Add it to `mark2.jar-path` in your mark2.properties
2. Specify the full path to the jar in `mark2 start`

### Shortcuts for running servers

If your servers all reside in one directory, you may want to add a start
helper to your path:

    #!/bin/bash
    mark2 start /path/to/servers/$1

And run it like

    mcstart pvp

Likewise if `mark2 attach -n blah` becomes a little too much, you could always
`alias at='mark2 attach -n'`
