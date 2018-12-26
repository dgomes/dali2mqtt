#!/usr/bin/env python3
__author__ = "Diogo Gomes"
__version__ = "0.0.1"
__email__ = "diogogomes@gmail.com"

import argparse
import logging
import yaml
import io
import re

import paho.mqtt.client as mqtt

import dali.gear.general as gear
import dali.exceptions
import dali.address as address
from dali.command import YesNoResponse, Response

HASSEB = "hasseb"
TRIDONIC = "tridonic"
DALI_DRIVERS = [HASSEB, TRIDONIC]

MQTT_BASE_TOPIC = "dali2mqtt"
MQTT_DALI2MQTT_STATUS = MQTT_BASE_TOPIC+"/status"
MQTT_STATE_TOPIC = MQTT_BASE_TOPIC+"/{}/light/status"
MQTT_COMMAND_TOPIC = MQTT_BASE_TOPIC+"/{}/light/switch"
MQTT_BRIGHTNESS_STATE_TOPIC = MQTT_BASE_TOPIC+"/{}/light/brightness/status"
MQTT_BRIGHTNESS_COMMAND_TOPIC = MQTT_BASE_TOPIC+"/{}/light/brightness/set"
MQTT_PAYLOAD_ON = b"ON"
MQTT_PAYLOAD_OFF = b"OFF"


log_format = '%(asctime)s %(levelname)s: %(message)s'
logging.basicConfig(format=log_format, level=logging.DEBUG)
logger = logging.getLogger(__name__)

def dali_scan(dali_driver, max_range=4):
    lamps = []
    for lamp in range(0,max_range):
        try:
            logging.debug("Search for Lamp {}".format(lamp))
            r = dali_driver.send(gear.QueryControlGearPresent(address.Short(lamp)))
            if isinstance(r, YesNoResponse) and r.value:
                lamps.append(lamp)
        except Exception as e:
            logger.error(e)
            #Not present
            logger.warning("%s not present", lamp)
    return lamps

def on_message_cmd(mosq, dalic, msg):
    logger.debug("Command on %s: %s", msg.topic, msg.payload)
    light = int(re.search(MQTT_COMMAND_TOPIC.format('(.+?)'), msg.topic).group(1))
    if msg.payload == MQTT_PAYLOAD_OFF:
        logger.debug("Set light <%s> to %s", light, msg.payload)
        dalic.send(gear.Off(address.Short(light)))
        mosq.publish(MQTT_STATE_TOPIC.format(light), MQTT_PAYLOAD_OFF)

def on_message_brightness_cmd(mosq, dalic, msg):
    logger.debug("Brightness Command on %s: %s", msg.topic, msg.payload)
    light = int(re.search(MQTT_BRIGHTNESS_COMMAND_TOPIC.format('(.+?)'), msg.topic).group(1))
    try:
        level = int(msg.payload.decode("utf-8"))
        if level < 0 or level > 255:
            raise ValueError
        logger.debug("Set light <%s> brightness to %s", light, level)
        r = dalic.send(gear.DAPC(address.Short(light), level))
        mosq.publish(MQTT_BRIGHTNESS_STATE_TOPIC.format(light), level)
    except ValueError as e:
        logger.error(e)
        logger.error("Can't convert <%s> to interger 0..255", level)

def on_message(mosq, dalic, msg):
    logger.error("Don't publish to %s", msg.topic)

def on_connect(client, dalic, flags, result):
    client.subscribe([(MQTT_COMMAND_TOPIC.format("+"),0), (MQTT_BRIGHTNESS_COMMAND_TOPIC.format("+"),0)])
    client.publish(MQTT_DALI2MQTT_STATUS,"1",retain=True)
    lamps = dali_scan(dalic)
    print(lamps)
    for lamp in lamps:
        try:
            r = dalic.send(gear.QueryActualLevel(address.Short(lamp)))
            logger.debug("QueryActualLevel = %s", r.value)
            client.publish(MQTT_BRIGHTNESS_STATE_TOPIC.format(lamp), r.value.as_integer, retain=True)
            client.publish(MQTT_STATE_TOPIC.format(lamp), MQTT_PAYLOAD_ON if r.value.as_integer > 0 else MQTT_PAYLOAD_OFF, retain=True)
        except Exception as e:
            logger.error(e)

def main_loop(driver, mqtt_server, mqtt_port):
    dalic = None
    logger.debug("Using <%s> driver", driver)
    if driver == HASSEB:
        from dali.driver.hasseb import SyncHassebDALIUSBDriver 
        dalic = SyncHassebDALIUSBDriver()
    elif driver == TRIDONIC:
        from dali.driver.tridonic import SyncTridonicDALIUSBDriver
        dalic = SyncTridonicDALIUSBDriver

    logger.debug("Connecting to %s:%s", mqtt_server, mqtt_port)
    mqttc = mqtt.Client(client_id="dali2mqtt", userdata=dalic)
    mqttc.will_set(MQTT_DALI2MQTT_STATUS,"0",retain=True)
    mqttc.on_connect = on_connect

    # Add message callbacks that will only trigger on a specific subscription match.
    mqttc.message_callback_add(MQTT_COMMAND_TOPIC.format('+'), on_message_cmd)
    mqttc.message_callback_add(MQTT_BRIGHTNESS_COMMAND_TOPIC.format('+'), on_message_brightness_cmd)
    mqttc.on_message = on_message
    mqttc.connect(mqtt_server, mqtt_port, 60)

    mqttc.loop_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="configuration file", default="config.ini")
    parser.add_argument("--mqtt-server", help="MQTT server", default="localhost")
    parser.add_argument("--mqtt-port", help="MQTT port", type=int, default=1883)
    parser.add_argument("--mqtt-base-topic", help="MQTT base topic", default=MQTT_BASE_TOPIC)
    parser.add_argument("--dali-driver", help="DALI device driver", choices=DALI_DRIVERS, default=HASSEB)

    args = parser.parse_args()

    config = {"mqtt_server": args.mqtt_server,
              "mqtt_port": args.mqtt_port,
              "dali_driver": args.dali_driver,
              }

    try:
        with open(args.config, 'r') as stream:
            logger.debug("Loading configuration from <%s>", args.config)
            config = yaml.load(stream)
    except FileNotFoundError:
        with io.open(args.config, 'w', encoding="utf8") as outfile:
            yaml.dump(config, outfile, default_flow_style=False, allow_unicode=True)

    main_loop(config["dali_driver"], config["mqtt_server"], config["mqtt_port"])
