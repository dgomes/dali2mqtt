#!/usr/bin/env python3
"""Bridge between a DALI controller and an MQTT bus."""

import argparse
import logging
import random
import re
import time
import os

import paho.mqtt.client as mqtt

import dali.address as address
import dali.gear.general as gear
from dali.command import YesNoResponse
from dali.exceptions import DALIError

from dali2mqtt.devicesnamesconfig import DevicesNamesConfig
from dali2mqtt.lamp import Lamp
from dali2mqtt.config import Config
from dali2mqtt.consts import (
    ALL_SUPPORTED_LOG_LEVELS,
    CONF_CONFIG,
    CONF_DALI_DRIVER,
    CONF_DALI_LAMPS,
    CONF_DEVICES_NAMES_FILE,
    CONF_HA_DISCOVERY_PREFIX,
    CONF_LOG_COLOR,
    CONF_LOG_LEVEL,
    CONF_MQTT_BASE_TOPIC,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_SERVER,
    CONF_MQTT_USERNAME,
    DALI_DRIVERS,
    DALI_SERVER,
    DEFAULT_CONFIG_FILE,
    DEFAULT_HA_DISCOVERY_PREFIX,
    HA_DISCOVERY_PREFIX,
    HASSEB,
    LOG_FORMAT,
    MAX_RETRIES,
    MIN_BACKOFF_TIME,
    MAX_BACKOFF_TIME,
    MIN_HASSEB_FIRMWARE_VERSION,
    MQTT_AVAILABLE,
    MQTT_BRIGHTNESS_COMMAND_TOPIC,
    MQTT_BRIGHTNESS_GET_COMMAND_TOPIC,
    MQTT_BRIGHTNESS_MAX_LEVEL_TOPIC,
    MQTT_BRIGHTNESS_MIN_LEVEL_TOPIC,
    MQTT_BRIGHTNESS_PHYSICAL_MINIMUM_LEVEL_TOPIC,
    MQTT_BRIGHTNESS_STATE_TOPIC,
    MQTT_COMMAND_TOPIC,
    MQTT_DALI2MQTT_STATUS,
    MQTT_NOT_AVAILABLE,
    MQTT_PAYLOAD_OFF,
    MQTT_PAYLOAD_ON,
    MQTT_SCAN_LAMPS_COMMAND_TOPIC,
    MQTT_STATE_TOPIC,
    RED_COLOR,
    TRIDONIC,
    YELLOW_COLOR,
)


logging.basicConfig(format=LOG_FORMAT, level=os.environ.get("LOGLEVEL", "INFO"))
logger = logging.getLogger(__name__)


def dali_scan(dali_driver):
    """Scan a maximum number of dali devices."""
    lamps = []
    for lamp in range(0, 63):
        try:
            logging.debug("Search for Lamp %s", lamp)
            present = dali_driver.send(
                gear.QueryControlGearPresent(address.Short(lamp))
            )
            if isinstance(present, YesNoResponse) and present.value:
                lamps.append(lamp)
                logger.debug("Found lamp at address %d", lamp)
        except DALIError as err:
            logger.warning("%s not present: %s", lamp, err)
    return lamps


def scan_groups(dali_driver, lamps):
    """Scan for groups."""
    logger.info("Scanning for groups")
    groups = {}
    for lamp in lamps:
        try:
            logging.debug("Search for groups for Lamp {}".format(lamp))
            group1 = dali_driver.send(
                gear.QueryGroupsZeroToSeven(address.Short(lamp))
            ).value.as_integer
            group2 = dali_driver.send(
                gear.QueryGroupsEightToFifteen(address.Short(lamp))
            ).value.as_integer

            #            logger.debug("Group 0-7: %d", group1)
            #            logger.debug("Group 8-15: %d", group2)

            lamp_groups = []

            for i in range(8):
                checkgroup = 1 << i
                logging.debug("Check pattern: %d", checkgroup)
                if (group1 & checkgroup) == checkgroup:
                    if i not in groups:
                        groups[i] = []
                    groups[i].append(lamp)
                    lamp_groups.append(i)
                if (group2 & checkgroup) != 0:
                    if not i + 8 in groups:
                        groups[i + 8] = []
                    groups[i + 8].append(lamp)
                    lamp_groups.append(i + 8)

            logger.debug("Lamp %d is in groups %s", lamp, lamp_groups)

        except Exception as e:
            logger.warning("Can't get groups for lamp %s: %s", lamp, e)
    logger.info("Finished scanning for groups")
    return groups


def initialize_lamps(data_object, client):
    """Initialize all lamps and groups."""

    driver = data_object["driver"]
    mqtt_base_topic = data_object["base_topic"]
    ha_prefix = data_object["ha_prefix"]
    log_level = data_object["log_level"]
    devices_names_config = data_object["devices_names_config"]
    devices_names_config.load_devices_names_file()
    lamps = dali_scan(driver)
    logger.info(
        "Found %d lamps",
        len(lamps),
    )

    def create_mqtt_lamp(address, name):
        try:
            lamp_object = Lamp(
                log_level,
                driver,
                name,
                address,
            )

            data_object["all_lamps"][name] = lamp_object

            mqtt_data = [
                (
                    HA_DISCOVERY_PREFIX.format(ha_prefix, name),
                    lamp_object.gen_ha_config(mqtt_base_topic),
                    True,
                ),
                (
                    MQTT_BRIGHTNESS_STATE_TOPIC.format(mqtt_base_topic, name),
                    lamp_object.level,
                    False,
                ),
                (
                    MQTT_BRIGHTNESS_MAX_LEVEL_TOPIC.format(mqtt_base_topic, name),
                    lamp_object.max_level,
                    True,
                ),
                (
                    MQTT_BRIGHTNESS_MIN_LEVEL_TOPIC.format(mqtt_base_topic, name),
                    lamp_object.min_level,
                    True,
                ),
                (
                    MQTT_BRIGHTNESS_PHYSICAL_MINIMUM_LEVEL_TOPIC.format(
                        mqtt_base_topic, name
                    ),
                    lamp_object.min_physical_level,
                    True,
                ),
                (
                    MQTT_STATE_TOPIC.format(mqtt_base_topic, name),
                    MQTT_PAYLOAD_ON if lamp_object.level > 0 else MQTT_PAYLOAD_OFF,
                    False,
                ),
            ]
            for topic, payload, retain in mqtt_data:
                client.publish(topic, payload, retain)

            logger.info(lamp_object)

        except DALIError as err:
            logger.error("While initializing <%s> @ %s: %s", name, address, err)

    for lamp in lamps:
        short_address = address.Short(lamp)

        create_mqtt_lamp(
            short_address,
            devices_names_config.get_friendly_name(short_address.address),
        )

    groups = scan_groups(driver, lamps)
    for group in groups:
        logger.debug("Publishing group %d", group)

        group_address = address.Group(int(group))

        create_mqtt_lamp(group_address, f"group_{group}")

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
            lamp_object.off()
            mqtt_client.publish(
                MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                MQTT_PAYLOAD_OFF,
                retain=True,
            )
        except DALIError as err:
            logger.error("Failed to set light <%s> to OFF: %s", light, err)
        except KeyError:
            logger.error("Lamp %s doesn't exists", light)


def on_message_reinitialize_lamps_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT scan lamps command message."""
    logger.debug("Reinitialize Command on %s", msg.topic)
    initialize_lamps(data_object, mqtt_client)


def get_lamp_object(data_object, light):
    """Retrieve lamp object from data object."""
    if "group_" in light:
        """Check if the comand is for a dali group"""
        group = int(re.search(r"group_(\d+)", light).group(1))
        lamp_object = data_object["all_lamps"][group]
    else:
        """The command is for a single lamp"""
        if light not in data_object["all_lamps"]:
            raise KeyError
        lamp_object = data_object["all_lamps"][light]
    return lamp_object


def on_message_brightness_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT brightness command message."""
    logger.debug("Brightness Command on %s: %s", msg.topic, msg.payload)
    light = re.search(
        MQTT_BRIGHTNESS_COMMAND_TOPIC.format(data_object["base_topic"], "(.+?)"),
        msg.topic,
    ).group(1)
    try:
        lamp_object = get_lamp_object(data_object, light)

        try:
            lamp_object.level = int(msg.payload.decode("utf-8"))
            if lamp_object.level == 0:
                # 0 in DALI is turn off with fade out
                lamp_object.off()
                logger.debug("Set light <%s> to OFF", light)

            mqtt_client.publish(
                MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                MQTT_PAYLOAD_ON if lamp_object.level != 0 else MQTT_PAYLOAD_OFF,
                retain=False,
            )
            mqtt_client.publish(
                MQTT_BRIGHTNESS_STATE_TOPIC.format(data_object["base_topic"], light),
                lamp_object.level,
                retain=True,
            )
        except ValueError as err:
            logger.error(
                "Can't convert <%s> to integer %d..%d: %s",
                msg.payload.decode("utf-8"),
                lamp_object.min_level,
                lamp_object.max_level,
                err,
            )
    except KeyError:
        logger.error("Lamp %s doesn't exists", light)


def on_message_brightness_get_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT brightness get command message."""
    logger.debug("Brightness Get Command on %s: %s", msg.topic, msg.payload)
    light = re.search(
        MQTT_BRIGHTNESS_GET_COMMAND_TOPIC.format(data_object["base_topic"], "(.+?)"),
        msg.topic,
    ).group(1)
    try:
        lamp_object = get_lamp_object(data_object, light)

        try:
            lamp_object.actual_level()
            logger.debug("Get light <%s> results in %d", light, lamp_object.level)

            mqtt_client.publish(
                MQTT_BRIGHTNESS_STATE_TOPIC.format(data_object["base_topic"], light),
                lamp_object.level,
                retain=False,
            )

            mqtt_client.publish(
                MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                MQTT_PAYLOAD_ON if lamp_object.level != 0 else MQTT_PAYLOAD_OFF,
                retain=False,
            )

        except ValueError as err:
            logger.error(
                "Can't convert <%s> to integer %d..%d: %s",
                lamp_object.level,
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
    client.subscribe(
        [
            (MQTT_COMMAND_TOPIC.format(mqtt_base_topic, "+"), 0),
            (MQTT_BRIGHTNESS_COMMAND_TOPIC.format(mqtt_base_topic, "+"), 0),
            (MQTT_BRIGHTNESS_GET_COMMAND_TOPIC.format(mqtt_base_topic, "+"), 0),
            (MQTT_SCAN_LAMPS_COMMAND_TOPIC.format(mqtt_base_topic), 0),
        ]
    )
    client.publish(
        MQTT_DALI2MQTT_STATUS.format(mqtt_base_topic), MQTT_AVAILABLE, retain=True
    )
    initialize_lamps(data_object, client)


def create_mqtt_client(
    driver,
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
            "driver": driver,
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
        MQTT_BRIGHTNESS_GET_COMMAND_TOPIC.format(mqtt_base_topic, "+"),
        on_message_brightness_get_cmd,
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


def main(args):
    """Main loop."""
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

    retries = 0
    while retries < MAX_RETRIES:
        try:
            mqttc = create_mqtt_client(
                dali_driver,
                *config.mqtt_conf,
                devices_names_config,
                config.ha_discovery_prefix,
                config.log_level,
            )
            mqttc.loop_forever()
            retries = (
                0  # if we reach here, it means we where already connected successfully
            )
        except Exception as e:
            logger.error("%s: %s", type(e).__name__, e)
            time.sleep(random.randint(MIN_BACKOFF_TIME, MAX_BACKOFF_TIME))
            retries += 1

    logger.error("Maximum retries of %d reached, exiting...", retries)


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
        f"--{CONF_MQTT_USERNAME.replace('_','-')}", help="MQTT username"
    )
    parser.add_argument(
        f"--{CONF_MQTT_PASSWORD.replace('_','-')}", help="MQTT password"
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
        f"--{CONF_DALI_LAMPS.replace('_','-')}",
        help="Number of lamps to scan",
        type=int,
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
