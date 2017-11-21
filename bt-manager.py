from flask import Flask
from flask import request
import BeaconData
from TemperatureScan import TemperatureScan
import json
import sys
import traceback
import logging
from datetime import datetime
from urllib import urlopen
import netifaces as ni

'''

Run with: FLASK_APP=bt-manager.py flask run --host=0.0.0.0

send config data with: 
curl -X POST --data @config.json --header "Content-Type:application/json" http://localhost:5000/config

start:  curl -X GET http://localhost:5000/start/{all,beacons,temperature}
stop:   curl -X GET http://localhost:5000/stop/{all,beacons,temperature}
status: curl -X GET http://localhost:5000
'''

app = Flask(__name__)
logging.basicConfig(filename="flask.log", level=logging.DEBUG)
logger = logging.getLogger(__name__)


total = 0
count = 0
config_loaded = False
config_stash = "/home/pi/bt/store-config.json"
config_version = None
scanner = None
temp_scanner = None

def init():
    global config_stash
    try:
        with open(config_stash,"r") as fp:
            cfg = json.load(fp)
        if 'name' in cfg and 'interface' in cfg and 'controller' in cfg:
            if cfg["interface"] in ni.interfaces():
                ip = ni.ifaddresses(cfg["interface"])[ni.AF_INET][0]['addr']
                info = {"name": cfg["name"], "controller": cfg["controller"], "address": ip, "interface": cfg["interface"]}
                r = urlopen(cfg["controller"], data="json="+json.dumps(info))
                logger.info("[%s] result from check-in: %s", str(datetime.now()), r.read())
            else:
                logger.warning("[%s] interface %s doesn't exist, can't check in", str(datetime.now()), cfg["interface"])
        else:
            logger.info("[%s] config doesn't have check-in items", str(datetime.now()))
        
    except Exception as e:
        type, value, tb = sys.exc_info()[:3]
        logger.warning("[%s] startup error encoutered: {%s}", str(datetime.now()), type)
        logger.warning(e, exc_info=True)
        logger.warning("[%s] startup error not-fatal, starting up", str(datetime.now()))
    
@app.route('/')
def running_status():
    global scanner, temp_scanner, config_version
    if scanner is None or not scanner._running:
        s = "stopped"
    else:
        s = "running"
    
    if temp_scanner is None or not temp_scanner._running:
        t = "stopped"
    else:
        t = "running"
        
    status = {"status":{"beacons":s,"temperature":t}, "version": config_version}
    return json.dumps(status)


@app.route('/config', methods=['POST'])
def load_config():
    global request, config_loaded, confg_stash, config_version
    try:
        data = json.loads(request.data)
        with open(config_stash,"w") as fp:
            json.dump(data,fp)
        config_version = data["version"]
        config_loaded = True
        return json.dumps({"status":"success"})
    except Exception as e:
        return handle_exception(e)


@app.route('/start/<ind>')
def start_publishing(ind):
    global config_loaded, scanner, temp_scanner
    try:
        if not config_loaded:
            return json.dumps({"status":"failure", "reason":"No configuration loaded"})
        else:
            if ind == "all" or ind == "beacons":
                scanner = BeaconData.BeaconScanAndPublish(config_stash)
                scanner.start()
            if ind == "all" or ind == "temperature":
                temp_scanner = TemperatureScan(config_stash)
                temp_scanner.start()
            return json.dumps({"status":"success"})
    except Exception as e:
        return handle_exception(e)

        
@app.route('/stop/<ind>')
def stop_publishing(ind):
    global config_loaded, config_stash, scanner, temp_scanner
    try:
        if (ind == "all" or ind == "beacons") and scanner is not None:
            scanner.stop()
            scanner = None
        if (ind == "all" or ind == "temperature") and temp_scanner is not None:
            temp_scanner.stop()
            temp_scanner = None
        return json.dumps({"status":"success"})
    except Exception as e:
        return handle_exception(e)

    
@app.route('/ble', methods=['POST'])
def show_payload():
    global count, total
    data = json.loads(request.data)
    print data["beacons"][0]["rssi"]

    total += float(data["beacons"][0]["rssi"])
    
    if count == 10:
        count = 0
        print "average: {0}".format(total/10)
    else:
        count += 1
    
    return "Done"

def handle_exception(e):
    type, value, tb = sys.exc_info()[:3]
    logger.error("[%s] error encoutered: {%s}", str(datetime.now()), type)
    logger.error(e, exc_info=True)
    s = {"status": "failure",
         "reason": str(type),
         "description": str(value)}
    return json.dumps(s)

init()
