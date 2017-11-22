# Overview

Before running, edit /home/bt/store-config.json and make sure the top level has:
* name - the name of this receiver
* interface - the network interface that the server can reach this receiver (eg: wlan0)
* controller - the URL for the check-in (eg: http://192.168.0.4/ble/check-in)

Invoke the script startup-flask.sh from /etc/rc.local

Run manually with: FLASK_APP=hello.py flask run --host=0.0.0.0

send config data with: 
curl -X POST --data @config.json --header "Content-Type:application/json" http://localhost:5000/config

start:  curl -X GET http://localhost:5000/start
stop:   curl -X GET http://localhost:5000/stop
status: curl -X GET http://localhost:5000

To run temperature scanner:

python scan-temperature.py -m tcp://208.184.212.178:1883 -f 5 -p /ATI/Beacons/MB_Pi -d Temp

Notes about the Beacons:

Lotton beacon programmed with BeaconFlyer app
Radius Networks beacon programmed with RadBeacon

All beacons have the URI set to: http://sdw.ati.com
Namespaces are "69788673717376657884" - ASCII codes of ENVIGILANT

Beacon passwords:
Lotton: 000000
Radius Networks: 0000-0000

# Installation

sudo pip install virtualenvwrapper

add to .bashrc:
export WORKON_HOME=$HOME/.virtualenvs
export PROJECT_HOME=$HOME/Devel
source /usr/local/bin/virtualenvwrapper.sh

mkvirtualenv bt
sudo apt-get install libbluetooth-dev libcap2-bin
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))
pip install beacontools[scan]
pip install Flask
pip install pyyaml
pip install netifaces
pip install paho-mqtt

install SDW

# BT-MQTT

Contains listener to MQTT for BLE beacon data

