Run with: FLASK_APP=hello.py flask run --host=0.0.0.0

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

# BT-MQTT

Contains listener to MQTT for BLE beacon data

