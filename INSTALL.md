# installation

## requirements

* UNIX-like operating system (Linux, Mac OS X, BSD)
* python 2.7
* psutil
* urwid
* twisted
* twisted-web
* twisted-words (for IRC support)
* feedparser (for RSS support)

### debian/ubuntu

This should suffice:

    $ sudo apt-get install python-twisted python-twisted-web python-twisted-words
    $ sudo pip install psutil urwid feedparser

### centos

CentOS and some other distros ship an older version of python. To find out your python version, run:

    $ python -V

If you get something lower than 2.7, first check you don't already have python 2.7 installed somewhere else. Type:

    $ python<TAB>

If you see `python2.7` you don't need to install again, but you will need to apply the patch listed below.

If you *don't* see `python2.7`, you need to install it. A decent guide for centos is
[located here](http://toomuchdata.com/2012/06/25/how-to-install-python-2-7-3-on-centos-6-2/). Be sure to follow the
instructions for installing `distribute also.

Next, install twisted from the package on [their website](http://twistedmatrix.com/). Don't use easy_install - you
won't get the binaries that ship with twisted.

easy_install for python 2.7 is probably in `/usr/local/bin/easy_install-2.7`. You should use it to install the remaining
mark2 dependencies:

    $ sudo /usr/local/bin/easy_install-2.7 psutil urwid feedparser

After installing mark2, make sure you apply the patch described later.

## installation

mark2 doesn't need to be installed to a particular directory, but if you have no reasonable ideas `/usr/mark2` will be
okay. First, download mark2:

    $ git clone https://github.com/mcdevs/mark2.git

If you don't have git (and you probably should!) you could:

    $ wget https://github.com/mcdevs/mark2/archive/master.tar.gz
    $ tar zxvf master.tar.gz
    $ rm master.tar.gz
    $ mv mark2-master mark2

Next, symlink the `mark2` script into your executable path:

    $ sudo ln -s /usr/mark2/mark2 /usr/bin/mark2

If you run mark2 on a server where you expect multiple system users to start servers, you *need* to create a dedicated
user to run servers under.

    $ sudo adduser mcservers

To start a server, either run `mark2 start` as `sudo -u mcservers mark2 start ...`, or assign a value to `java.user` in
`/config/mark2.properties` and start with `sudo mark2 start ...`

### python patch

If your python 2.7 executable isn't at `/usr/bin/python`, you need to apply a small patch to mark2. Open
`/usr/mark2/mark2` and edit the path in the first line to point to the right place. On CentOS it probably wants to
read `#!/usr/local/bin/python2.7`.

### tips

If your server has a strange name, you have a couple of options:

1. add it to `mark2.jar-path` in your mark2.properties
2. specify the full path to the jar in `mark2 start`

If your servers all reside in one directory, you may want to add a start
helper to your path:

    #!/bin/bash
    mark2 start /path/to/servers/$1

And run it like

    $ mcstart pvp

Likewise if `mark2 attach -n blah` becomes a little too much, you could always
`alias at='mark2 attach -n'`



