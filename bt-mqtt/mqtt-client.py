import paho.mqtt.client as mqtt
import requests
import json
import time
from datetime import datetime
from urllib import urlopen
from dateutil import parser
import calendar

'''
' Uses dateutil package, installed with 'pip install python-dateutil'
'''

beacon_index = {}
receiver_index = {}

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("sdw/#")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global beacon_index, receiver_index
    if 'value' in msg.topic:
        o = json.loads(msg.payload)
        unix_time = calendar.timegm(parser.parse(o['datetime']).timetuple())
        for v in o['values']:
            if 'beacon' in v['attributes'] and 'receiver' in v['attributes']:
                beacon = v['attributes']['beacon']
                receiver = v['attributes']['receiver']
                update = {
                    "keys": {
                        'field_beacon': beacon_index[beacon]['nid'],
                        'field_receiver': receiver_index[receiver]['nid']
                        },
                    "values": {
                        'title': "{0} @ {1}".format(beacon,receiver),
                        'field_rssi': v['amount'],
                        'field_timestamp': unix_time
                    }
                }
                fp = urlopen("http://localhost/rest/bt_beacon_detection", data="json="+json.dumps(update))
                print "[{0}]: {1}".format(datetime.now().strftime('%r'),fp.read())
            else:
                print "Missing needed attributes: {0}".format(o)
    elif 'status' in msg.topic:
        o = json.loads(msg.payload)
        if 'attributes' not in o:
            print "No attribute in payload: {0}".format(msg.payload)
        elif 'receiver' in o['attributes']:
            receiver = o['attributes']['receiver']
            update = {
                "keys": {
                    'nid': receiver_index[receiver]['nid']
                },
                "values": {
                    'field_receiver_status': o['status']
                }
            }
            fp = urlopen("http://localhost/rest/bt_receiver", data="json="+json.dumps(update))
            print fp.read()
        else:
            print "Missing needed attributes: {0}".format(o)
        
# Load all of the known entities of a given type into an index
def load_objects(content_type,key,fields):
    index = {}
    r = requests.get('http://localhost/rest/query/' + content_type)
    if r.ok:
        for o in r.json():
            obj = {}
            k = o[key]
            for f in fields:
                obj[f] = o[f]
            index[k] = obj
    else:
        print "Error from GET: " . r.reason
    return index

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 1883, 60)

beacon_index = load_objects('bt_beacon', 'title', ['nid'])
receiver_index = load_objects('bt_receiver', 'title', ['nid'])

print 'Beacons: {0}'.format(beacon_index)
print 'Receivers: {0}'.format(receiver_index)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
