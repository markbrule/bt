import paho.mqtt.client as mqtt
import requests
import json
import time
import logging
from datetime import datetime
from urllib import urlopen
from dateutil import parser
import calendar
import re

''' 
' Configuration Items
'
' "server"          - protocol, server address/name, and port that runs the MQTT broker
' "keepalive"       - seconds for keepalive on connect
' "topic"           - MQTT topic to subscribe to (eg: sdw/#)
' "object_endpoint" - WS endpoint for node-content-rest (eg: http://(lamp)/rest)
'''


class MqttListener:
    def __init__(self):
        self._cfg = None
        self._client = None
        self._ready_to_run = False
        self._running = False
        self._subscribed_to = None
        self._beacons = {}
        self._receivers = {}
        self._last_error = None
        self._logger = logging.getLogger(__name__)

    def reload_configuration(self, config):
        self._cfg = config
        m = re.match('([a-z]*://)?([^:/]+)?:?([0-9]+)?', self._cfg['server'])
        self._cfg['port'] = 1883 if m.group(3) == '' else int(m.group(3))
        self._cfg['server'] = m.group(2)
        self._ready_to_run = False
        self._client = mqtt.Client()
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        self._client.connect(self._cfg['server'], int(self._cfg['port']), int(self._cfg['keepalive']))

        self._beacons = self.load_objects('bt_beacon', 'title', ['nid'])
        if self._beacons is None:
            return False
        else:
            self._logger.info("[%s] loaded beacons [%s]", str(datetime.now()),
                              reduce(lambda x,y: "{0} {1}".format(x,y), [z for z in self._beacons]))

        self._receivers = self.load_objects('bt_receiver', 'title', ['nid'])
        if self._receivers is None:
            return False
        else:
            self._logger.info("[%s] loaded receivers [%s]", str(datetime.now()),
                              reduce(lambda x,y: "{0} {1}".format(x,y), [z for z in self._receivers]))

        self._ready_to_run = True
        return True
    
    def stop(self):
        if self._running:
            self._client.loop_stop()
            self._running = False
            self._logger.info("[%s] MQTT listener stopped", str(datetime.now()))
        else:
            self._logger.info("[%s] request to stop MQTT listener that wasn't started", str(datetime.now()))
            
    def start(self):
        if self._running:
            self._logger.info("[%s] MQTT start requested, stopping first", str(datetime.now()))
            self.stop()
        
        if not self._ready_to_run:
            self._last_error = "[{0}] broker not ready to run".format(str(datetime.now()))
            self._logger.error(self._last_error)
            return False
        
        self._logger.info("[%s] starting listener", str(datetime.now()))
        self._client.loop_start()
        return True


    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        code = {0: "Connection successful",
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorised"}[rc]
        self._logger.info("[%s] connected to broker with result code: %s", str(datetime.now()), code)
        if rc == 0:
            self._client.subscribe(self._cfg['topic'])
            self._logger.info("[%s] connected to topic %s", str(datetime.now()), self._cfg['topic'])
        else:
            self._last_error = "[{0}] failed to connect because: {1}".format(str(datetime.now()), code)
            self._logger.error(self._last_error)


    def on_message(self, client, userdata, msg):
        if 'value' in msg.topic:
            o = json.loads(msg.payload)
            unix_time = calendar.timegm(parser.parse(o['datetime']).timetuple())
            for v in o['values']:
                if 'beacon' in v['attributes'] and 'receiver' in v['attributes']:
                    beacon = v['attributes']['beacon']
                    receiver = v['attributes']['receiver']

                    if beacon not in self._beacons:
                        self._beacons = load_objects('bt_beacon', 'title', ['nid'])
                        if beacon not in self._beacons:
                            self._logger.info("[%s] Beacon %s not found, skipping", str(datetime.now()), beacon)
                            continue

                    if receiver not in self._receivers:
                        self._receivers = load_objects('bt_receiver', 'title', ['nid'])
                        if receiver not in self._receiver:
                            self._logger.info("[%s] Receiver %s not found, skipping", str(datetime.now()), receiver)
                            continue
                            
                    update = {
                        "keys": {
                            'field_beacon': self._beacons[beacon]['nid'],
                            'field_receiver': self._receivers[receiver]['nid'],
                            'field_detection_mode': 'live'
                        },
                        "values": {
                            'title': "{0} @ {1}".format(beacon,receiver),
                            'field_rssi': v['amount'],
                            'field_timestamp': unix_time
                        }
                    }
                    fp = urlopen(self._cfg['object_endpoint'] + "/bt_beacon_detection", data="json="+json.dumps(update))
                    self._logger.info("[%s] Data post results: %s", str(datetime.now()), fp.read())
                else:
                    self._logger.info("[%s] Missing needed attributes: %s", str(datetime.now()), o)
        elif 'status' in msg.topic:
            o = json.loads(msg.payload)
            if 'attributes' not in o:
                self._logger.info("[%s] No attribute in payload: %s", str(datetime.now()), msg.payload)
            elif 'receiver' in o['attributes']:
                receiver = o['attributes']['receiver']
                update = {
                    "keys": {
                        'nid': self._receivers[receiver]['nid']
                    },
                    "values": {
                        'field_receiver_status': o['status']
                    }
                }
                fp = urlopen(self._cfg['object_endpoint'] + "/bt_receiver", data="json="+json.dumps(update))
                self._logger.info("[%s] Status post results: %s", str(datetime.now()), fp.read())
        else:
            self._logger.info("[%s] Missing needed attributes: %s", str(datetime.now()), o)


    #
    # Helper function to load all the objects of a particular type and create an index
    #
    def load_objects(self, content_type, key, fields):
        index = {}
        r = requests.get(self._cfg['object_endpoint'] + '/query/' + content_type)
        if r.ok:
            for o in r.json():
                obj = {}
                k = o[key]
                for f in fields:
                    obj[f] = o[f]
                    index[k] = obj
        else:
            self._last_error = "[{0}] Error building object index [{1}]: {2}".format(str(datetime.now()), content_type, r.reason)
            self._logger.error(self._last_error)
            return None
        
        return index
