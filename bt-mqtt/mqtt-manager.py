from flask import Flask
from flask import request
from MqttListener import MqttListener
import json
import sys
import traceback
import logging
from datetime import datetime
from urllib import urlopen
import os

'''
' Run with: FLASK_APP=bt-manager.py flask run --host=0.0.0.0
'
' send config data with: 
'
' curl -X POST --data @config.json --header "Content-Type:application/json" http://localhost:5000/config
' start:  curl -X GET http://localhost:5000/start
' stop:   curl -X GET http://localhost:5000/stop
' status: curl -X GET http://localhost:5000
'''

app = Flask(__name__)
logging.basicConfig(filename=os.getcwd()+"/mqtt-manager.log", level=logging.DEBUG)
logger = logging.getLogger(__name__)


total = 0
count = 0
config_loaded = False
config_stash = os.getcwd()+"/store-config.json"
config_version = None
listener = None

def init():
    global config_stash, config_loaded, listener
    try:
        with open(config_stash,"r") as fp:
            cfg = json.load(fp)
            listener = MqttListener()
            if listener.reload_configuration(cfg):
                config_loaded = True
                
    except Exception as e:
        type, value, tb = sys.exc_info()[:3]
        logger.warning("[%s] startup error encoutered: {%s}", str(datetime.now()), type)
        logger.warning(e, exc_info=True)
        logger.warning("[%s] startup error not-fatal, starting up", str(datetime.now()))
    
@app.route('/status')
def running_status():
    global listener
    if listener is None:
        s = "no listener"
    elif not listener._running:
        if listener._ready_to_run:
            s = "stopped, ready"
        else:
            s = "stopped, not ready"
    else:
        s = "running"
    
    if listener is None or listener._cfg is None:
        topic = "None"
    else:
        topic = listener._cfg['topic']
        
    status = {"status": s, "topic": topic}
    return json.dumps(status)


@app.route('/config', methods=['POST'])
def load_config():
    global request, config_loaded, confg_stash, listener
    try:
        data = json.loads(request.data)
        with open(config_stash,"w") as fp:
            json.dump(data,fp)
        listener.reload_configuration(data)
        config_loaded = True
        return json.dumps({"status":"success"})
    except Exception as e:
        return handle_exception(e)


@app.route('/start')
def start_publishing():
    global config_loaded, listener
    try:
        if not config_loaded:
            return json.dumps({"status":"failure", "reason":"No configuration loaded"})
        else:
            listener.start()
            return json.dumps({"status":"success"})
    except Exception as e:
        return handle_exception(e)

        
@app.route('/stop')
def stop_publishing(ind):
    global listener
    try:
        listener.stop()
        return json.dumps({"status":"success"})
    except Exception as e:
        return handle_exception(e)

    

def handle_exception(e):
    type, value, tb = sys.exc_info()[:3]
    logger.error("[%s] error encoutered: {%s}", str(datetime.now()), type)
    logger.error(e, exc_info=True)
    s = {"status": "failure",
         "reason": str(type),
         "description": str(value)}
    return json.dumps(s)

init()
