import yaml
import json
import logging
import sdw
import time
from threading import Thread, Event
from datetime import datetime

import os

logger = logging.getLogger(__name__)


class TemperatureScan(Thread):
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
        self._cfg = temp['temperature']
        mqttaddr = self._cfg['mqtt']
        if mqttaddr.startswith("tcp://"):
            mqttaddr = mqttaddr[6:]
        addr, port = mqttaddr.split(":")
        self._path = self._cfg["sensor"]
        self._pub = sdw.MQTT(addr, int(port), self._path)
        self._frequency = float(self._cfg["frequency"]) / 1000
        self._field = self._cfg["field"]

    def measure_temp(self):
        temp = os.popen("vcgencmd measure_temp").readline()
        return float(temp.replace("temp=","").replace("'C",""))


    def stop(self):
        self._stop_event.set()
        if self._pub is not None:
            self._pub.publish_status("NOT_RUNNING")
        logger.debug("[%s] stopped publishing temperature", str(datetime.now()))
            

    def run(self):
        if self._cfg is None:
            logger.error("[%s] no configuration loaded, can't start temperature pub", str(datetime.now()))
            return

        self._pub.publish_status("RUNNING")
        self._running = True
        while not self._stop_event.is_set():
            t = self.measure_temp()
            payload = [ self._pub.create_value(self._field, t) ]
            success = self._pub.publish_values(payload)
            if success:
                logger.debug("[%s] temperature published %f to %s:%s", str(datetime.now()), float(t), self._path, self._field)
            else:
                logger.error("[%s] error publishing temperature %f on %s:%s", str(datetime.now()), t, self._path, self._field)
            time.sleep(self._frequency)

        logger.info("[%s] Stop Event received - shutting down temperature publisher", str(datetime.now()))
        self._running = False
