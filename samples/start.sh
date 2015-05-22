#!/bin/sh
# mark2 Spigot restart script
# restart-on-crash: false
# restart-script: ./start.sh

BASEDIR=`dirname $0`
sleep 1
mark2 start $BASEDIR