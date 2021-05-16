#!/usr/bin/env python3
"""Bridge between a DALI controller and an MQTT bus."""


import argparse
import io
import logging
import re
import yaml
import random
import time

import paho.mqtt.client as mqtt
import dali.address as address
import dali.gear.general as gear
from dali.command import YesNoResponse
from dali.exceptions import DALIError

from config import Config
from lamp import Lamp
from devicesnamesconfig import DevicesNamesConfig

from consts import (
    DALI_DRIVERS,
    DALI_SERVER,
    DEFAULT_CONFIG_FILE,
    DEFAULT_DEVICES_NAMES_FILE,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_SERVER,
    DEFAULT_HA_DISCOVERY_PREFIX,
    DEFAULT_MQTT_BASE_TOPIC,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_COLOR,
    CONF_CONFIG,
    CONF_DEVICES_NAMES_FILE,
    CONF_DALI_DRIVER,
    CONF_DALI_LAMPS,
    CONF_LOG_COLOR,
    CONF_LOG_LEVEL,
    CONF_HA_DISCOVERY_PREFIX,
    CONF_MQTT_BASE_TOPIC,
    CONF_MQTT_PORT,
    CONF_MQTT_SERVER,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    HA_DISCOVERY_PREFIX,
    HASSEB,
    MIN_HASSEB_FIRMWARE_VERSION,
    MQTT_AVAILABLE,
    MQTT_BRIGHTNESS_COMMAND_TOPIC,
    MQTT_BRIGHTNESS_STATE_TOPIC,
    MQTT_SCAN_LAMPS_COMMAND_TOPIC,
    MQTT_COMMAND_TOPIC,
    MQTT_DALI2MQTT_STATUS,
    MQTT_NOT_AVAILABLE,
    MQTT_PAYLOAD_OFF,
    MQTT_PAYLOAD_ON,
    MQTT_STATE_TOPIC,
    MQTT_BRIGHTNESS_MAX_LEVEL_TOPIC,
    MQTT_BRIGHTNESS_MIN_LEVEL_TOPIC,
    MQTT_BRIGHTNESS_PHYSICAL_MINIMUM_LEVEL_TOPIC,
    ALL_SUPPORTED_LOG_LEVELS,
    TRIDONIC,
    MIN_BACKOFF_TIME,
    MAX_RETRIES,
    RESET_COLOR,
    RED_COLOR,
    YELLOW_COLOR,
    LOG_FORMAT,
)

logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def dali_scan(driver):
    """Scan a maximum number of dali devices."""
    lamps = []
    for lamp in range(0, 63):
        try:
            logging.debug("Search for Lamp %s", lamp)
            present = driver.send(gear.QueryControlGearPresent(address.Short(lamp)))
            if isinstance(present, YesNoResponse) and present.value:
                lamps.append(lamp)
        except DALIError as err:
            logger.warning("%s not present: %s", lamp, err)
    return lamps


def initialize_lamps(data_object, client):
    driver_object = data_object["driver"]
    mqtt_base_topic = data_object["base_topic"]
    ha_prefix = data_object["ha_prefix"]
    log_level = data_object["log_level"]
    devices_names_config = data_object["devices_names_config"]
    devices_names_config.load_devices_names_file()
    lamps = dali_scan(driver_object)
    logger.info(
        "Found %d lamps",
        len(lamps),
    )
    for lamp in lamps:
        try:
            short_address = address.Short(lamp)
            actual_level = driver_object.send(gear.QueryActualLevel(short_address))
            physical_minimum = driver_object.send(
                gear.QueryPhysicalMinimum(short_address)
            )
            min_level = driver_object.send(gear.QueryMinLevel(short_address))
            max_level = driver_object.send(gear.QueryMaxLevel(short_address))
            device_name = devices_names_config.get_friendly_name(short_address.address)
            lamp = device_name

            lamp_object = Lamp(
                log_level,
                driver_object,
                device_name,
                short_address,
                physical_minimum.value,
                min_level.value,
                actual_level.value,
                max_level.value,
            )

            data_object["all_lamps"][lamp_object.device_name] = lamp_object
            lamp = lamp_object.device_name

            client.publish(
                HA_DISCOVERY_PREFIX.format(ha_prefix, lamp),
                lamp_object.gen_ha_config(mqtt_base_topic),
                retain=True,
            )
            client.publish(
                MQTT_BRIGHTNESS_STATE_TOPIC.format(mqtt_base_topic, lamp),
                actual_level.value,
                retain=True,
            )

            client.publish(
                MQTT_BRIGHTNESS_MAX_LEVEL_TOPIC.format(mqtt_base_topic, lamp),
                max_level.value,
                retain=True,
            )
            client.publish(
                MQTT_BRIGHTNESS_MIN_LEVEL_TOPIC.format(mqtt_base_topic, lamp),
                min_level.value,
                retain=True,
            )
            client.publish(
                MQTT_BRIGHTNESS_PHYSICAL_MINIMUM_LEVEL_TOPIC.format(
                    mqtt_base_topic, lamp
                ),
                physical_minimum.value,
                retain=True,
            )
            client.publish(
                MQTT_STATE_TOPIC.format(mqtt_base_topic, lamp),
                MQTT_PAYLOAD_ON if actual_level.value > 0 else MQTT_PAYLOAD_OFF,
                retain=True,
            )
            logger.info(
                "   - short address: %d, actual brightness level: %d (minimum: %d, max: %d, physical minimum: %d)",
                short_address.address,
                actual_level.value,
                min_level.value,
                max_level.value,
                physical_minimum.value,
            )

        except DALIError as err:
            logger.error("While initializing lamp<%s>: %s", lamp, err)

    if devices_names_config.is_devices_file_empty():
        devices_names_config.save_devices_names_file(data_object["all_lamps"])
    logger.info("initialize_lamps finished")


def on_detect_changes_in_config(mqtt_client):
    """Callback when changes are detected in the configuration file."""
    logger.info("Reconnecting to server")
    mqtt_client.disconnect()


def on_message_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT command message."""
    logger.debug("Command on %s: %s", msg.topic, msg.payload)
    light = re.search(
        MQTT_COMMAND_TOPIC.format(data_object["base_topic"], "(.+?)"), msg.topic
    ).group(1)
    if msg.payload == MQTT_PAYLOAD_OFF:
        try:
            lamp_object = data_object["all_lamps"][light]
            logger.debug("Set light <%s> to %s", light, msg.payload)
            data_object["driver"].send(gear.Off(lamp_object.short_address))
            mqtt_client.publish(
                MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                MQTT_PAYLOAD_OFF,
                retain=True,
            )
        except DALIError as err:
            logger.error("Failed to set light <%s> to %s: %s", light, "OFF", err)
        except KeyError:
            logger.error("Lamp %s doesn't exists", light)


def on_message_reinitialize_lamps_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT scan lamps command message"""
    logger.debug("Reinitialize Command on %s", msg.topic)
    initialize_lamps(data_object, mqtt_client)


def on_message_brightness_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT brightness command message."""
    logger.debug("Brightness Command on %s: %s", msg.topic, msg.payload)
    light = re.search(
        MQTT_BRIGHTNESS_COMMAND_TOPIC.format(data_object["base_topic"], "(.+?)"),
        msg.topic,
    ).group(1)
    try:
        if light not in data_object["all_lamps"]:
            raise KeyError
        lamp_object = data_object["all_lamps"][light]
        level = None
        try:
            level = msg.payload.decode("utf-8")
            level = int(level)
            lamp_object.level = level
            if lamp_object.level == 0:
                # 0 in DALI is turn off with fade out
                mqtt_client.publish(
                    MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                    MQTT_PAYLOAD_OFF,
                    retain=True,
                )
                data_object["driver"].send(gear.Off(lamp_object.short_address.address))
                logger.debug("Set light <%s> to OFF", light)

            else:
                mqtt_client.publish(
                    MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                    MQTT_PAYLOAD_ON,
                    retain=True,
                )
            mqtt_client.publish(
                MQTT_BRIGHTNESS_STATE_TOPIC.format(data_object["base_topic"], light),
                lamp_object.level,
                retain=True,
            )
        except ValueError as err:
            logger.error(
                "Can't convert <%s> to integer %d..%d: %s",
                str(level),
                lamp_object.min_level,
                lamp_object.max_level,
                err,
            )
    except KeyError:
        logger.error("Lamp %s doesn't exists", light)


def on_message(mqtt_client, data_object, msg):  # pylint: disable=W0613
    """Default callback on MQTT message."""
    logger.error("Don't publish to %s", msg.topic)


def on_connect(
    client,
    data_object,
    flags,
    result,
    ha_prefix=DEFAULT_HA_DISCOVERY_PREFIX,
):  # pylint: disable=W0613,R0913
    """Callback on connection to MQTT server."""
    mqtt_base_topic = data_object["base_topic"]
    driver_object = data_object["driver"]
    client.subscribe(
        [
            (MQTT_COMMAND_TOPIC.format(mqtt_base_topic, "+"), 0),
            (MQTT_BRIGHTNESS_COMMAND_TOPIC.format(mqtt_base_topic, "+"), 0),
            (MQTT_SCAN_LAMPS_COMMAND_TOPIC.format(mqtt_base_topic), 0),
        ]
    )
    client.publish(
        MQTT_DALI2MQTT_STATUS.format(mqtt_base_topic), MQTT_AVAILABLE, retain=True
    )
    initialize_lamps(data_object, client)


def create_mqtt_client(
    driver_object,
    mqtt_server,
    mqtt_port,
    mqtt_username,
    mqtt_password,
    mqtt_base_topic,
    devices_names_config,
    ha_prefix,
    log_level,
):
    """Create MQTT client object, setup callbacks and connection to server."""
    logger.debug("Connecting to %s:%s", mqtt_server, mqtt_port)
    mqttc = mqtt.Client(
        client_id="dali2mqtt",
        userdata={
            "driver": driver_object,
            "base_topic": mqtt_base_topic,
            "ha_prefix": ha_prefix,
            "devices_names_config": devices_names_config,
            "log_level": log_level,
            "all_lamps": {},
        },
    )
    mqttc.will_set(
        MQTT_DALI2MQTT_STATUS.format(mqtt_base_topic), MQTT_NOT_AVAILABLE, retain=True
    )
    mqttc.on_connect = lambda a, b, c, d: on_connect(a, b, c, d, ha_prefix)

    # Add message callbacks that will only trigger on a specific subscription match.
    mqttc.message_callback_add(
        MQTT_COMMAND_TOPIC.format(mqtt_base_topic, "+"), on_message_cmd
    )
    mqttc.message_callback_add(
        MQTT_BRIGHTNESS_COMMAND_TOPIC.format(mqtt_base_topic, "+"),
        on_message_brightness_cmd,
    )
    mqttc.message_callback_add(
        MQTT_SCAN_LAMPS_COMMAND_TOPIC.format(mqtt_base_topic),
        on_message_reinitialize_lamps_cmd,
    )
    mqttc.on_message = on_message
    if mqtt_username:
        mqttc.username_pw_set(mqtt_username, mqtt_password)
    mqttc.connect(mqtt_server, mqtt_port, 60)
    return mqttc


def delay():
    return MIN_BACKOFF_TIME + random.randint(0, 1000) / 1000.0


def main(args):
    mqttc = None
    config = Config(args, lambda: on_detect_changes_in_config(mqttc))

    if config.log_color:
        logging.addLevelName(
            logging.WARNING,
            "{}{}".format(YELLOW_COLOR, logging.getLevelName(logging.WARNING)),
        )
        logging.addLevelName(
            logging.ERROR, "{}{}".format(RED_COLOR, logging.getLevelName(logging.ERROR))
        )

    logger.setLevel(ALL_SUPPORTED_LOG_LEVELS[config.log_level])
    devices_names_config = DevicesNamesConfig(
        config.log_level, config.devices_names_file
    )

    dali_driver = None
    logger.debug("Using <%s> driver", config.dali_driver)

    if config.dali_driver == HASSEB:
        from dali.driver.hasseb import SyncHassebDALIUSBDriver

        dali_driver = SyncHassebDALIUSBDriver()

        firmware_version = float(dali_driver.readFirmwareVersion())
        if firmware_version < MIN_HASSEB_FIRMWARE_VERSION:
            logger.error("Using dali2mqtt requires newest hasseb firmware")
            logger.error(
                "Please, look at https://github.com/hasseb/python-dali/tree/master/dali/driver/hasseb_firmware"
            )
            quit(1)
    elif config.dali_driver == TRIDONIC:
        from dali.driver.tridonic import SyncTridonicDALIUSBDriver

        dali_driver = SyncTridonicDALIUSBDriver()
    elif config.dali_driver == DALI_SERVER:
        from dali.driver.daliserver import DaliServer

        dali_driver = DaliServer("localhost", 55825)

    should_backoff = True
    retries = 0
    run = True
    while run:
        mqttc = create_mqtt_client(
            dali_driver,
            *config.mqtt_conf,
            devices_names_config,
            config.ha_discovery_prefix,
            config.log_level,
        )
        mqttc.loop_forever()
        if should_backoff:
            if retries == MAX_RETRIES:
                run = False
            time.sleep(delay())
            retries += 1  # TODO reset on successfull connection


if __name__ == "__main__":
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    parser.add_argument(
        f"--{CONF_CONFIG}", help="configuration file", default=DEFAULT_CONFIG_FILE
    )
    parser.add_argument(
        f"--{CONF_DEVICES_NAMES_FILE.replace('_','-')}", help="devices names file"
    )
    parser.add_argument(f"--{CONF_MQTT_SERVER.replace('_','-')}", help="MQTT server")
    parser.add_argument(
        f"--{CONF_MQTT_PORT.replace('_','-')}", help="MQTT port", type=int
    )
    parser.add_argument(
        f"--{CONF_MQTT_BASE_TOPIC.replace('_','-')}", help="MQTT base topic"
    )
    parser.add_argument(
        f"--{CONF_DALI_DRIVER.replace('_','-')}",
        help="DALI device driver",
        choices=DALI_DRIVERS,
    )
    parser.add_argument(
        f"--{CONF_HA_DISCOVERY_PREFIX.replace('_','-')}",
        help="HA discovery mqtt prefix",
    )
    parser.add_argument(
        f"--{CONF_LOG_LEVEL.replace('_','-')}",
        help="Log level",
        choices=ALL_SUPPORTED_LOG_LEVELS,
    )
    parser.add_argument(
        f"--{CONF_LOG_COLOR.replace('_','-')}",
        help="Coloring output",
        action="store_true",
    )

    args = parser.parse_args()

    main(args)
