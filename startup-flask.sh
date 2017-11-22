#!/bin/bash
#
# Simple script to start up Flask on reboot. Invoke this script in /etc/rc.local
#
export HOME=/home/pi
export WORKON_HOME=$HOME/.virtualenvs
source /usr/local/bin/virtualenvwrapper.sh
workon bt
cd $HOME/bt
FLASK_APP=$HOME/bt/bt-manager.py flask run --host=0.0.0.0 > /dev/null 2>&1 < /dev/null &

