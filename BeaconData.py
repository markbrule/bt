import yaml
import json
import logging
import sdw
import time
from threading import Thread, Event
from datetime import datetime
from beacontools import BeaconScanner, EddystoneTLMFrame, EddystoneFilter


logger = logging.getLogger(__name__)


'''

Support classes for managing the publication of BLE (Eddystone) Beacons to Sensor Awareness

BeaconScanAndPublish - threaded control class for capturing data and publishing them
BeaconData           - coordinates the collection of data from the beacons
BeaconPublisher      - support for publishing beacon data to Sensor Awareness' MQTT server

'''

class BeaconScanAndPublish(Thread):
    def __init__(self, configFile):
        Thread.__init__(self)
        self._stop_event = Event()
        self._running = False
        self._cfg = None
        if configFile is not None:
            self.reload_configuration(configFile)
        

    def reload_configuration(self, configFile):
        with open(configFile) as fp:
            if configFile.endswith("yaml"):
                temp = yaml.safe_load(fp)
            else:
                temp = json.load(fp)

        self._cfg = temp['beacons']
        self._name = self._cfg['name']
        
        if self._cfg['mode'] not in ['last', 'mean', 'min', 'max']:
            logger.error("[%s] unrecognized mode: %s", str(datetime.now()), self._cfg['mode'])
            exit()
        
        # sensor_lut maps UID of the sensor to the path and field name
        self._sensor_lut = {}
        for m in self._cfg['mappings']:
            self._sensor_lut[m['sensor']] = {'path': m['path'], 'field': m['field']}

        # list of all the sensor UIDs and paths
        self._sensor_ids = map(lambda x: x['sensor'], self._cfg['mappings'])
        self._sensor_paths = [ self._sensor_lut[x]['path'] for x in self._sensor_ids ]

        self._beacons = BeaconData()
        self._publishers = BeaconPublisher(self._name)
        self._publishers.create_pubs(self._cfg['mqtt'], self._sensor_paths)

        self._logged_missing_ids = []
        self._scanner = None


    def beacon_callback(self, bt_addr, rssi, packet, add_info):
        key = add_info['instance']
        if key in self._sensor_ids:
            self._beacons.update_beacon(self._sensor_lut[key]['path'], rssi)
        else:
            if key not in self._logged_missing_ids:
                self._logged_missing_ids.append(key)
                logger.warning("[%s]: Encountered unknown beacon %s", datetime.now(), key)
        

    def stop(self):
        self._stop_event.set()
        if self._publishers is not None:
            self._publishers.publish_status_all("NOT_RUNNING")

        
    def run(self):
        if self._cfg is None:
            logger.error("[%s] no configuration loaded, can't start scanner", str(datetime.now()))
            return
        
        if self._scanner is None:
            self._scanner = BeaconScanner(self.beacon_callback,
                                          device_filter=EddystoneFilter(namespace=self._cfg['namespace']))
        self._scanner.start()
        self._running = True
        self._publishers.publish_status_all("RUNNING")
        logger.info("[%s] starting scanner", str(datetime.now()))
        while not self._stop_event.is_set():
            self._beacons.reset_all_beacons(self._sensor_paths)
            time.sleep(float(self._cfg['frequency'])/1000)
            logger.debug("[%s] scan data collected", str(datetime.now()))
            for x in self._sensor_ids:
                b = self._beacons.get_beacon(self._sensor_lut[x]['path'])
                if b[self._cfg['mode']] is not None:
                    path = self._sensor_lut[x]['path']
                    field = self._sensor_lut[x]['field']
                    logger.debug("[%s] %f on %d samples", path + ":" + field, b[self._cfg['mode']], b['count'])
                    self._publishers.publish_beacon(x, path, field, b[self._cfg['mode']])
        logger.info("[%s] Stop Event received - shutting down publisher", str(datetime.now()))
        self._scanner.stop()
        self._scanner = None
        self._running = False
        

class BeaconData:
    def __init__(self):
        self._data = {}
        

    # reset sensor data for all sensors beacons named in the list
    def reset_all_beacons(self, sensor_list):
        map(lambda s: self.reset_beacon(s), sensor_list)
            

    # reset the sensor data for a single beacon
    def reset_beacon(self, s):
        self._data[s] = { 'count': 0,
                          'total': 0,
                          'min': None,
                          'max': None,
                          'last': None,
                          'time': None,
                          'mean': None }
        
    # update the data for a specific beacon
    def update_beacon(self, s, rssi):
        if s not in self._data.keys():
            logger.warning("[%s] unrecognized sensor %s", str(datetime.now()), s)
        else:
            d = self.get_beacon(s)
            d['count'] += 1
            d['total'] += rssi
            d['last'] = rssi
            d['mean'] = float(d['total']) / d['count']
            if d['min'] is None or rssi < d['min']:
                d['min'] = rssi
            if d['max'] is None or rssi > d['max']:
                d['max'] = rssi
            

    # return the data object for a single beacon
    def get_beacon(self, s):
        return self._data[s]



class BeaconPublisher(Thread):
    def __init__(self, name):
        Thread.__init__(self)
        self._name = name
        self._pubs = {}


    # create publication objects for a list of paths
    # path_list is an array of SA paths
    def create_pubs(self, mqttaddr, path_list):
        if mqttaddr.startswith("tcp://"):
            mqttaddr = mqttaddr[6:]
        addr, port = mqttaddr.split(":")
        for p in path_list:
            self._pubs[p] = sdw.MQTT(addr, int(port), p)


    # publish status to a sensor, adding the receiver name as an attribute
    def publish_status(self, key, status):
        payload = self._pubs[key].create_status_payload(status, "")
        payload['attributes'] = {}
        payload['attributes']['receiver'] = self._name
        return self._pubs[key].publish("status", payload)
    

    # publish the status to all SA sensors
    # status is one of "RUNNING", "NOT_RUNNING", or "ERROR"
    def publish_status_all(self, status):
        s = map(lambda k: self.publish_status(k, status), self._pubs.keys())
        logger.info("[%s] sensor paths: %s", str(datetime.now()), self._pubs.keys())
        logger.debug("[%s] status publication result: %s", str(datetime.now()), str(s))


    # publish a beacon's RSSI
    def publish_beacon(self, uid, path, field, value):
        try:
            payload = self._pubs[path].create_value(field, float(value))
            payload['attributes']['receiver'] = self._name
            payload['attributes']['beacon'] = uid
            success = self._pubs[path].publish_values([payload])
            if not success:
                logger.error("[%s] error publishing %f on %s:%s", str(datetime.now()), float(value), path, field)
            else:
                logger.debug("[%s] published %f to %s:%s", str(datetime.now()), float(value), path, field)
        except ValueError:
            logger.error("[%s] value error on %s sending to %s:%s", str(datetime.now()), value, path, field)


