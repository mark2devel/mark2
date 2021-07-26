# Installation

## Note

If you are updating from the Python 2 version of mark2, please ensure you install the dependencies in your Python 3 site-packages. Failure to do so will result in errors.

## Pre-Requirements

* A UNIX-like operating system (Linux, Mac OS X, BSD)
* Python 3+

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

    sudo apt-get install python3-pip
    sudo pip3 install -r requirements.txt

### Arch

    pacman -S --needed python python-psutil python-urwid python-twisted python-service-identity python-feedparser python-pyopenssl

The `--needed` flag will skip packages already installed.

### CentOS

    sudo yum install python3-pip
    sudo pip3 install -r requirements.txt

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
