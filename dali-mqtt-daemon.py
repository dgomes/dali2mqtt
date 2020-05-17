#!/usr/bin/env python3
__author__ = "Diogo Gomes"
__version__ = "0.0.1"
__email__ = "diogogomes@gmail.com"

import argparse
import logging
import yaml
import json
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

LOG_LEVELS=logging._levelToName.values()
DEFAULT_LOG_LEVEL="INFO"

DEFAULT_MQTT_BASE_TOPIC = "dali2mqtt"
DEFAULT_HA_DISCOVERY_PREFIX = "homeassistant"

MQTT_BASE_TOPIC = DEFAULT_MQTT_BASE_TOPIC
MQTT_DALI2MQTT_STATUS = "{}/status"
MQTT_STATE_TOPIC = "{}/{}/light/status"
MQTT_COMMAND_TOPIC = "{}/{}/light/switch"
MQTT_BRIGHTNESS_STATE_TOPIC = "{}/{}/light/brightness/status"
MQTT_BRIGHTNESS_COMMAND_TOPIC = "{}/{}/light/brightness/set"
MQTT_PAYLOAD_ON = b"ON"
MQTT_PAYLOAD_OFF = b"OFF"
MQTT_AVAILABLE = "online"
MQTT_NOT_AVAILABLE = "offline"

HA_DISCOVERY_PREFIX="{}/light/dali2mqtt_{}/config"

def gen_ha_config(light):
    json_config = {
        "name": "DALI Light {}".format(light),
        "unique_id": "DALI2MQTT_LIGHT_{}".format(light),
        "state_topic": MQTT_STATE_TOPIC.format(MQTT_BASE_TOPIC,light),
        "command_topic": MQTT_COMMAND_TOPIC.format(MQTT_BASE_TOPIC,light), 
        "payload_off": MQTT_PAYLOAD_OFF.decode("utf-8"),
        "brightness_state_topic": MQTT_BRIGHTNESS_STATE_TOPIC.format(MQTT_BASE_TOPIC,light), 
        "brightness_command_topic": MQTT_BRIGHTNESS_COMMAND_TOPIC.format(MQTT_BASE_TOPIC,light), 
        "brightness_scale": 254,
        "on_command_type": 'brightness',
        "availability_topic": MQTT_DALI2MQTT_STATUS.format(MQTT_BASE_TOPIC),
        "payload_available": MQTT_AVAILABLE,
        "payload_not_available": MQTT_NOT_AVAILABLE,
        "device": {
                    "identifiers":"dali2mqtt",
                    "name": "DALI Lights",
                    "sw_version":"dali2mqtt 0.1",
                    "model":"dali2mqtt",
                    "manufacturer":"diogogomes@gmail.com"
                    }
    }
    return json.dumps(json_config)

def dali_scan(dali_driver, max_range=4):
    lamps = []
    for lamp in range(0,max_range):
        try:
            logging.debug("Search for Lamp {}".format(lamp))
            r = dali_driver.send(gear.QueryControlGearPresent(address.Short(lamp)))
            if isinstance(r, YesNoResponse) and r.value:
                lamps.append(lamp)
        except Exception as e:
            logger.warning("%s not present: %s", lamp, e, exc_info=True)
    return lamps

def scan_groups(dali_driver, lamps):
    groups = dict.fromkeys(range(16), [])
    for lamp in lamps:
        try:
            logging.debug("Search for groups for Lamp {}".format(lamp))
            group1 = dali_driver.send(gear.QueryGroupsZeroToSeven(address.Short(lamp))).value.as_integer
            group2 = dali_driver.send(gear.QueryGroupsEightToFifteen(address.Short(lamp))).value.as_integer
            
            lamp_groups = []

            for i in range(8):
                if (group1 & 1<<i) != 0:
                    groups[i].append(lamp)
                    lamp_groups.append(i)
            for i in range(8):
                if (group2 & 1<<i) != 0:
                    groups[i+7].append(lamp)
                    lamp_groups.append(i+8)
            logging.debug("Lamp {} is in groups {}".format(lamp, lamp_groups))
        except Exception as e:
            logger.warning("Can't get groups for lamp %s: %s", lamp, e)
    return groups

def on_message_cmd(mosq, dalic, msg):
    logger.debug("Command on %s: %s", msg.topic, msg.payload)
    light = int(re.search(MQTT_COMMAND_TOPIC.format(MQTT_BASE_TOPIC, '(.+?)'), msg.topic).group(1))
    if msg.payload == MQTT_PAYLOAD_OFF:
        try:
            logger.debug("Set light <%s> to %s", light, msg.payload)
            dalic.send(gear.Off(address.Short(light)))
            mosq.publish(MQTT_STATE_TOPIC.format(MQTT_BASE_TOPIC, light), MQTT_PAYLOAD_OFF, retain=True)
        except:
            logger.error("Failed to set light <%s> to %s", light, "OFF")

def on_message_brightness_cmd(mosq, dalic, msg):
    logger.debug("Brightness Command on %s: %s", msg.topic, msg.payload)
    light = int(re.search(MQTT_BRIGHTNESS_COMMAND_TOPIC.format(MQTT_BASE_TOPIC, '(.+?)'), msg.topic).group(1))
    try:
        level = int(msg.payload.decode("utf-8"))
        if not 0 <= level <= 255:
            raise ValueError
        logger.debug("Set light <%s> brightness to %s", light, level)
        r = dalic.send(gear.DAPC(address.Short(light), level))
        if level == 0:
            # 0 in DALI is turn off with fade out
            mosq.publish(MQTT_STATE_TOPIC.format(MQTT_BASE_TOPIC, light), MQTT_PAYLOAD_OFF, retain=True)
        else:
            mosq.publish(MQTT_STATE_TOPIC.format(MQTT_BASE_TOPIC, light), MQTT_PAYLOAD_ON, retain=True)
        mosq.publish(MQTT_BRIGHTNESS_STATE_TOPIC.format(MQTT_BASE_TOPIC, light), level, retain=True)
    except ValueError as e:
        logger.error("Can't convert <%s> to interger 0..255: %s", level, e)

def on_message(mosq, dalic, msg):
    logger.error("Don't publish to %s", msg.topic)

def on_connect(client, dalic, flags, result, max_lamps=4, ha_prefix=DEFAULT_HA_DISCOVERY_PREFIX):
    client.subscribe([(MQTT_COMMAND_TOPIC.format(MQTT_BASE_TOPIC, "+"),0), (MQTT_BRIGHTNESS_COMMAND_TOPIC.format(MQTT_BASE_TOPIC, "+"),0)])
    client.publish(MQTT_DALI2MQTT_STATUS.format(MQTT_BASE_TOPIC),MQTT_AVAILABLE,retain=True)
    lamps = dali_scan(dalic, max_lamps)
    groups = scan_groups(dalic, lamps)
    for lamp in lamps:
        try:
            r = dalic.send(gear.QueryActualLevel(address.Short(lamp)))
            logger.debug("QueryActualLevel = %s", r.value)
            client.publish(HA_DISCOVERY_PREFIX.format(ha_prefix, lamp), gen_ha_config(lamp), retain=True)
            client.publish(MQTT_BRIGHTNESS_STATE_TOPIC.format(MQTT_BASE_TOPIC, lamp), r.value, retain=True)
            client.publish(MQTT_STATE_TOPIC.format(MQTT_BASE_TOPIC, lamp), MQTT_PAYLOAD_ON if r.value > 0 else MQTT_PAYLOAD_OFF, retain=True)
        except Exception as e:
            logger.error("While initializing lamp<%s>: %s", lamp, e)

def main_loop(config):
    dalic = None
    logger.debug("Using <%s> driver", config["dali_driver"])
    if config["dali_driver"] == HASSEB:
        from dali.driver.hasseb import SyncHassebDALIUSBDriver 
        dalic = SyncHassebDALIUSBDriver()
    elif config["dali_driver"] == TRIDONIC:
        from dali.driver.tridonic import SyncTridonicDALIUSBDriver
        dalic = SyncTridonicDALIUSBDriver()

    logger.debug("Connecting to %s:%s", config["mqtt_server"], config["mqtt_port"])
    mqttc = mqtt.Client(client_id="dali2mqtt", userdata=dalic)
    mqttc.will_set(MQTT_DALI2MQTT_STATUS.format(MQTT_BASE_TOPIC),MQTT_NOT_AVAILABLE,retain=True)
    mqttc.on_connect = lambda a,b,c,d: on_connect(a,b,c,d, config["dali_lamps"], config["ha_discover_prefix"])

    # Add message callbacks that will only trigger on a specific subscription match.
    mqttc.message_callback_add(MQTT_COMMAND_TOPIC.format(MQTT_BASE_TOPIC, '+'), on_message_cmd)
    mqttc.message_callback_add(MQTT_BRIGHTNESS_COMMAND_TOPIC.format(MQTT_BASE_TOPIC, '+'), on_message_brightness_cmd)
    mqttc.on_message = on_message

    #Set userid and password
    mqttc.username_pw_set(config["mqtt_user"], config["mqtt_password"])

    mqttc.connect(config["mqtt_server"], config["mqtt_port"], 60)

    mqttc.loop_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="configuration file", default="config.yml")
    parser.add_argument("--mqtt-server", help="MQTT server", default="localhost")
    parser.add_argument("--mqtt-port", help="MQTT port", type=int, default=1883)
    parser.add_argument("--mqtt-base-topic", help="MQTT base topic", default=DEFAULT_MQTT_BASE_TOPIC)
    parser.add_argument("--mqtt-user", help="MQTT user")
    parser.add_argument("--mqtt-password", help="MQTT password")
    parser.add_argument("--log-level", help="Logger level", choices=LOG_LEVELS, default=DEFAULT_LOG_LEVEL)
    parser.add_argument("--dali-driver", help="DALI device driver", choices=DALI_DRIVERS, default=HASSEB)
    parser.add_argument("--dali-lamps", help="Number of lamps to scan", type=int, default=4)
    parser.add_argument("--ha-discover-prefix", help="HA discover mqtt prefix", default="homeassistant")

    args = parser.parse_args()

    config = {"mqtt_server": args.mqtt_server,
              "mqtt_port": args.mqtt_port,
              "mqtt_base_topic": args.mqtt_base_topic,
              "mqtt_user": args.mqtt_user,
              "mqtt_password": args.mqtt_password,
              "log_level": args.log_level,
              "dali_driver": args.dali_driver,
              "dali_lamps": args.dali_lamps,
              "ha_discover_prefix": args.ha_discover_prefix,
              }
    
    try:
        with open(args.config, 'r') as stream:
            config = yaml.load(stream)

        log_format = '%(asctime)s %(levelname)s: %(message)s'
        logging.basicConfig(format=log_format, level=logging.getLevelName(config["log_level"]))
        logger = logging.getLogger(__name__)

        MQTT_BASE_TOPIC = config["mqtt_base_topic"]

        main_loop(config)
    except FileNotFoundError as e:
        logger.info("Configuration file %s created, please reload daemon", args.config)
    except KeyError as e:
        missing_key = e.args[0]
        config[missing_key] = args.__dict__[missing_key]
        logger.info("Configuration file updated, please reload daemon")
    finally:
        with io.open(args.config, 'w', encoding="utf8") as outfile:
            yaml.dump(config, outfile, default_flow_style=False, allow_unicode=True)

