#!/bin/sh
# mark2 Spigot restart script
# restart-on-crash: false
# restart-script: ./start.sh

mark2 send -n ${PWD##*/} ~restart
