#!/usr/bin/env python3
"""Bridge between a DALI controller and an MQTT bus."""

import re
import traceback
from pprint import pprint
import random
import time

import paho.mqtt.client as mqtt
import dali.address as address
import dali.gear.general as gear
from dali.command import YesNoResponse
from dali.exceptions import DALIError

from .config import Config
from .group import Group
from .lamp import Lamp
from .devicesnamesconfig import DevicesNamesConfig

from .consts import *
logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)

def dali_scan(driver):
    """Scan a maximum number of dali devices."""
    lamps = []
    config = Config()
    for lamp in range(0, 64):
        try:
            logger.debug("Search for Lamp %s", lamp)
            present = driver.send(gear.QueryControlGearPresent(address.Short(lamp)))
            if isinstance(present, YesNoResponse) and present.value:
                lamps.append(lamp)
                logger.debug("Found lamp at address %d", lamp)
                if len(lamps) >= config[CONF_DALI_LAMPS]:
                    logger.warning("All %s configured lamps have been found, Stopping scan",  config[CONF_DALI_LAMPS])
                    return lamps
        except DALIError as err:
            logger.warning("%s not present: %s", lamp, err)

    logger.info("Found %d lamps", len(lamps))
    return lamps

def scan_groups(dali_driver, lamps):
    logger.info("Scanning for groups")
    groups = {}
    for lamp in lamps:
        try:
            logger.debug("Search for groups for Lamp {}".format(lamp))
            group1 = dali_driver.send(gear.QueryGroupsZeroToSeven(address.Short(lamp))).value.as_integer
            group2 = dali_driver.send(gear.QueryGroupsEightToFifteen(address.Short(lamp))).value.as_integer

#            logger.debug("Group 0-7: %d", group1)
#            logger.debug("Group 8-15: %d", group2)

            lamp_groups = []

            for i in range(8):
                checkgroup = 1<<i
                logger.debug("Check pattern: %d", checkgroup)
                if (group1 & checkgroup) == checkgroup:
                    if not i in groups:
                      groups[i]=[]
                    groups[i].append(lamp)
                    lamp_groups.append(i)
                if (group2 & checkgroup) != 0:
                    if not i+8 in groups:
                      groups[i+8]=[]
                    groups[i+8].append(lamp)
                    lamp_groups.append(i+8)
            
            logger.debug("Lamp %d is in groups %s",lamp, lamp_groups)
            
        except Exception as e:
            logger.warning("Can't get groups for lamp %s: %s", lamp, e)
    logger.info("Finished scanning for groups")
    return groups

def initialize_lamps(data_object, client):
    driver_object = data_object["driver"]
    lamps = dali_scan(driver_object)
    
    for lamp in lamps:
        try:
            _address = address.Short(lamp)
            lamp = Lamp(driver_object, client, _address)
            data_object["all_lamps"][lamp.address] = lamp

        except Exception as err:
            logger.error("While initializing lamp<%s>: %s", lamp, err)
            print(traceback.format_exc())
            raise err

    groups = scan_groups(driver_object, lamps)
    for group, group_lamps in groups.items():
        try:
            _address = address.Group(group)
            _lamps = []
            for _x in group_lamps:
                _lamps.append(data_object["all_lamps"][_x])
            group = Group(driver_object, client, _address, _lamps)
            for _x in group_lamps:
                data_object["all_lamps"][_x].addGroup(group)
            data_object["all_groups"][group.address] = group

        except Exception as err:
            logger.error("While initializing group<%s>: %s", group, err)
            print(traceback.format_exc())
            raise err

    devices_names_config = DevicesNamesConfig()
    if devices_names_config.is_devices_file_empty():
        devices_names_config.save_devices_names_file(list(data_object["all_lamps"].values()) + list(data_object["all_groups"].values()))

    config = Config()
    client.publish(
        MQTT_DALI2MQTT_STATUS.format(config[CONF_MQTT_BASE_TOPIC]), MQTT_AVAILABLE, retain=True
    )
    logger.info("initialize_lamps finished")

def on_message_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT command message."""
    logger.debug("Command on %s: %s", msg.topic, msg.payload)
    config = Config()
    rex = re.search(MQTT_COMMAND_TOPIC.format(config[CONF_MQTT_BASE_TOPIC], "(.+?)-(.+?)"), msg.topic)
    type = rex.group(1)
    light = int(rex.group(2))
    if type not in ["lamp", "group"]:
        logger.error(f"Received invalid type: {type}")
        return

    if msg.payload == MQTT_PAYLOAD_OFF:
        try:
            if type == "lamp":
                obj = data_object["all_lamps"][light]
            else:
                obj = data_object["all_groups"][light]
            try:
                obj.setLevel(0)
                logger.debug(f"Set {obj.device_name} to OFF")
            except DALIError as err:
                logger.error(f"Failed to set {obj.device_name} to OFF: {err}")
        except KeyError:
            logger.error(f"{type} {light} doesn't exists")


def on_message_reinitialize_lamps_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT scan lamps command message"""
    logger.debug("Reinitialize Command on %s", msg.topic)
    config = Config()
    mqtt_client.publish(
        MQTT_DALI2MQTT_STATUS.format(config[CONF_MQTT_BASE_TOPIC]), MQTT_NOT_AVAILABLE, retain=True
    )
    initialize_lamps(data_object, mqtt_client)

def on_message_poll_lamps_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT poll lamps command message"""
    logger.info("Poll lamps command on %s", msg.topic)
    for _x in data_object["all_lamps"].values():
        _x.pollLevel()
    for _x in data_object["all_groups"].values():
        _x.recalc_level()

def get_lamp_object(data_object,light):
    if 'group_' in light:
        """ Check if the comand is for a dali group """
        group = int(re.search('group_(\d+)', light).group(1))
        lamp_object=data_object["all_lamps"][group]
    else:
        """ The command is for a single lamp """
        if light not in data_object["all_lamps"]:
            raise KeyError
        lamp_object = data_object["all_lamps"][light]
    return lamp_object


def on_message_brightness_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT brightness command message."""
    logger.debug("Brightness Command on %s: %s", msg.topic, msg.payload)

    config = Config()
    rex = re.search(MQTT_BRIGHTNESS_COMMAND_TOPIC.format(config[CONF_MQTT_BASE_TOPIC], "(.+?)-(.+?)"), msg.topic)
    type = rex.group(1)
    light = int(rex.group(2))
    level = msg.payload.decode("utf-8")

    if type not in ["lamp", "group"]:
        logger.error(f"Received invalid type: {type}")
        return

    if level.isdigit() and 0 <= int(level) < 256:
        level = int(level)
        try:
            if type == "lamp":
                obj = data_object["all_lamps"][light]
            else:
                obj = data_object["all_groups"][light]
            try:
                obj.setLevel(level)
                logger.debug(f"Set {obj.device_name} to {level}")
            except DALIError as err:
                logger.error(f"Failed to set {obj.device_name} to OFF: {err}")
        except KeyError:
            logger.error(f"{type} {light} doesn't exists")
    else:
        logger.error(f"Invalid payload for {type} {light}")

def on_message(mqtt_client, data_object, msg):  # pylint: disable=W0613
    """Default callback on MQTT message."""
    logger.error("Don't publish to %s", msg.topic)


def on_connect(client, data_object, flags, result):  # pylint: disable=W0613,R0913
    """Callback on connection to MQTT server."""
    config = Config()
    client.subscribe(
        [
            (MQTT_COMMAND_TOPIC.format(config[CONF_MQTT_BASE_TOPIC], "+"), 0),
            (MQTT_BRIGHTNESS_COMMAND_TOPIC.format(config[CONF_MQTT_BASE_TOPIC], "+"), 0),
            (MQTT_SCAN_LAMPS_COMMAND_TOPIC.format(config[CONF_MQTT_BASE_TOPIC]), 0),
            (MQTT_POLL_LAMPS_COMMAND_TOPIC.format(config[CONF_MQTT_BASE_TOPIC]), 0),
        ]
    )
    client.publish(
        MQTT_DALI2MQTT_STATUS.format(config[CONF_MQTT_BASE_TOPIC]), MQTT_NOT_AVAILABLE, retain=True
    )
    initialize_lamps(data_object, client)


def create_mqtt_client(driver_object):
    """Create MQTT client object, setup callbacks and connection to server."""

    config = Config()
    logger.debug("Connecting to %s:%s", config[CONF_MQTT_SERVER], config[CONF_MQTT_PORT])
    mqttc = mqtt.Client(
        client_id="dali2mqttx",
        userdata={
            "driver": driver_object,
            "all_lamps": {},
            "all_groups": {}
        },
    )
    mqttc.will_set(
        MQTT_DALI2MQTT_STATUS.format(config[CONF_MQTT_BASE_TOPIC]), MQTT_NOT_AVAILABLE, retain=True
    )
    mqttc.on_connect = on_connect

    # Add message callbacks that will only trigger on a specific subscription match.
    mqttc.message_callback_add(
        MQTT_COMMAND_TOPIC.format(config[CONF_MQTT_BASE_TOPIC], "+"), on_message_cmd
    )
    mqttc.message_callback_add(
        MQTT_BRIGHTNESS_COMMAND_TOPIC.format(config[CONF_MQTT_BASE_TOPIC], "+"),
        on_message_brightness_cmd,
    )
    mqttc.message_callback_add(
        MQTT_SCAN_LAMPS_COMMAND_TOPIC.format(config[CONF_MQTT_BASE_TOPIC]),
        on_message_reinitialize_lamps_cmd,
    )
    mqttc.message_callback_add(
        MQTT_POLL_LAMPS_COMMAND_TOPIC.format(config[CONF_MQTT_BASE_TOPIC]),
        on_message_poll_lamps_cmd,
    )

    mqttc.on_message = on_message

    if config[CONF_MQTT_USERNAME] != '':
        mqttc.username_pw_set(config[CONF_MQTT_USERNAME], config[CONF_MQTT_PASSWORD])

    mqttc.connect(config[CONF_MQTT_SERVER], config[CONF_MQTT_PORT], 60)
    return mqttc


def delay():
    return MIN_BACKOFF_TIME + random.randint(0, 1000) / 1000.0


def main(args):
    config = Config()
    config.setup(args)

    if config[CONF_LOG_COLOR]:
        logging.addLevelName(
            logging.WARNING,
            "{}{}".format(YELLOW_COLOR, logging.getLevelName(logging.WARNING)),
        )
        logging.addLevelName(
            logging.ERROR, "{}{}".format(RED_COLOR, logging.getLevelName(logging.ERROR))
        )

    logger.setLevel(ALL_SUPPORTED_LOG_LEVELS[config[CONF_LOG_LEVEL]])
    devices_names_config = DevicesNamesConfig()
    devices_names_config.setup()

    dali_driver = None
    logger.debug("Using <%s> driver", config[CONF_DALI_DRIVER])

    if config[CONF_DALI_DRIVER] == HASSEB:
        from dali.driver.hasseb import SyncHassebDALIUSBDriver

        dali_driver = SyncHassebDALIUSBDriver()

        firmware_version = float(dali_driver.readFirmwareVersion())
        if firmware_version < MIN_HASSEB_FIRMWARE_VERSION:
            logger.error("Using dali2mqtt requires newest hasseb firmware")
            logger.error(
                "Please, look at https://github.com/hasseb/python-dali/tree/master/dali/driver/hasseb_firmware"
            )
            quit(1)
    elif config[CONF_DALI_DRIVER] == TRIDONIC:
        from dali.driver.tridonic import SyncTridonicDALIUSBDriver

        dali_driver = SyncTridonicDALIUSBDriver()
    elif config[CONF_DALI_DRIVER] == DALI_SERVER:
        from dali.driver.daliserver import DaliServer

        dali_driver = DaliServer("localhost", 55825)

    mqttc = create_mqtt_client(dali_driver)
    mqttc.loop_forever()