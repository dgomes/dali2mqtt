#!/usr/bin/env python3
"""Bridge between a DALI controller and an MQTT bus."""
__author__ = "Diogo Gomes"
__version__ = "0.0.1"
__email__ = "diogogomes@gmail.com"

import argparse
import io
import json
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

from consts import (
    DALI_DRIVERS,
    DALI_SERVER,
    DEFAULT_CONFIG_FILE,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_SERVER,
    DEFAULT_DALI_DRIVER,
    DEFAULT_HA_DISCOVERY_PREFIX,
    DEFAULT_MQTT_BASE_TOPIC,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_COLOR,
    HA_DISCOVERY_PREFIX,
    HASSEB,
    MQTT_AVAILABLE,
    MQTT_BRIGHTNESS_COMMAND_TOPIC,
    MQTT_BRIGHTNESS_STATE_TOPIC,
    MQTT_COMMAND_TOPIC,
    MQTT_DALI2MQTT_STATUS,
    MQTT_NOT_AVAILABLE,
    MQTT_PAYLOAD_OFF,
    MQTT_PAYLOAD_ON,
    MQTT_STATE_TOPIC,
    ALL_SUPPORTED_LOG_LEVELS,
    TRIDONIC,
    MIN_BACKOFF_TIME,
    MAX_RETRIES,
    RESET_COLOR,
    RED_COLOR,
    YELLOW_COLOR,
)


log_format = "%(asctime)s %(levelname)s: %(message)s{}".format(RESET_COLOR)
logging.basicConfig(format=log_format)
logger = logging.getLogger(__name__)


def gen_ha_config(light, mqtt_base_topic):
    """Generate a automatic configuration for Home Assistant."""
    json_config = {
        "name": "DALI Light {}".format(light),
        "unique_id": "DALI2MQTT_LIGHT_{}".format(light),
        "state_topic": MQTT_STATE_TOPIC.format(mqtt_base_topic, light),
        "command_topic": MQTT_COMMAND_TOPIC.format(mqtt_base_topic, light),
        "payload_off": MQTT_PAYLOAD_OFF.decode("utf-8"),
        "brightness_state_topic": MQTT_BRIGHTNESS_STATE_TOPIC.format(
            mqtt_base_topic, light
        ),
        "brightness_command_topic": MQTT_BRIGHTNESS_COMMAND_TOPIC.format(
            mqtt_base_topic, light
        ),
        "brightness_scale": 254,
        "on_command_type": "brightness",
        "availability_topic": MQTT_DALI2MQTT_STATUS.format(mqtt_base_topic),
        "payload_available": MQTT_AVAILABLE,
        "payload_not_available": MQTT_NOT_AVAILABLE,
        "device": {
            "identifiers": "dali2mqtt",
            "name": "DALI Lights",
            "sw_version": f"dali2mqtt {__version__}",
            "model": "dali2mqtt",
            "manufacturer": f"{__author__} <{__email__}>",
        },
    }
    return json.dumps(json_config)


def dali_scan(driver, max_range=4):
    """Scan a maximum number of dali devices."""
    lamps = []
    for lamp in range(0, max_range):
        try:
            logging.debug("Search for Lamp %s", lamp)
            present = driver.send(gear.QueryControlGearPresent(address.Short(lamp)))
            if isinstance(present, YesNoResponse) and present.value:
                lamps.append(lamp)
        except DALIError as err:
            logger.warning("%s not present: %s", lamp, err)
    return lamps


def on_detect_changes_in_config(mqtt_client):
    """Callback when changes are detected in the configuration file."""
    logger.info("Reconnecting to server")
    mqtt_client.disconnect()


def on_message_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT command message."""
    logger.debug("Command on %s: %s", msg.topic, msg.payload)
    light = int(
        re.search(
            MQTT_COMMAND_TOPIC.format(data_object["base_topic"], "(.+?)"), msg.topic
        ).group(1)
    )
    if msg.payload == MQTT_PAYLOAD_OFF:
        try:
            logger.debug("Set light <%s> to %s", light, msg.payload)
            data_object["driver"].send(gear.Off(address.Short(light)))
            mqtt_client.publish(
                MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                MQTT_PAYLOAD_OFF,
                retain=True,
            )
        except DALIError as err:
            logger.error("Failed to set light <%s> to %s: %s", light, "OFF", err)


def on_message_brightness_cmd(mqtt_client, data_object, msg):
    """Callback on MQTT brightness command message."""
    logger.debug("Brightness Command on %s: %s", msg.topic, msg.payload)
    light = int(
        re.search(
            MQTT_BRIGHTNESS_COMMAND_TOPIC.format(data_object["base_topic"], "(.+?)"),
            msg.topic,
        ).group(1)
    )
    try:
        level = int(msg.payload.decode("utf-8"))
        if not 0 <= level <= 255:
            raise ValueError
        logger.debug("Set light <%s> brightness to %s", light, level)
        data_object["driver"].send(gear.DAPC(address.Short(light), level))
        if level == 0:
            # 0 in DALI is turn off with fade out
            mqtt_client.publish(
                MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                MQTT_PAYLOAD_OFF,
                retain=True,
            )
        else:
            mqtt_client.publish(
                MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                MQTT_PAYLOAD_ON,
                retain=True,
            )
        mqtt_client.publish(
            MQTT_BRIGHTNESS_STATE_TOPIC.format(data_object["base_topic"], light),
            level,
            retain=True,
        )
    except ValueError as err:
        logger.error("Can't convert <%s> to interger 0..255: %s", level, err)


def on_message(mqtt_client, data_object, msg):  # pylint: disable=W0613
    """Default callback on MQTT message."""
    logger.error("Don't publish to %s", msg.topic)


def on_connect(
    client,
    data_object,
    flags,
    result,
    max_lamps=4,
    ha_prefix=DEFAULT_HA_DISCOVERY_PREFIX,
):  # pylint: disable=W0613,R0913
    """Callback on connection to MQTT server."""
    mqtt_base_topic = data_object["base_topic"]
    driver_object = data_object["driver"]
    client.subscribe(
        [
            (MQTT_COMMAND_TOPIC.format(mqtt_base_topic, "+"), 0),
            (MQTT_BRIGHTNESS_COMMAND_TOPIC.format(mqtt_base_topic, "+"), 0),
        ]
    )
    client.publish(
        MQTT_DALI2MQTT_STATUS.format(mqtt_base_topic), MQTT_AVAILABLE, retain=True
    )
    lamps = dali_scan(driver_object, max_lamps)
    for lamp in lamps:
        try:
            actual_level = driver_object.send(
                gear.QueryActualLevel(address.Short(lamp))
            )
            logger.debug("QueryActualLevel = %s", actual_level.value)
            client.publish(
                HA_DISCOVERY_PREFIX.format(ha_prefix, lamp),
                gen_ha_config(lamp, mqtt_base_topic),
                retain=True,
            )
            client.publish(
                MQTT_BRIGHTNESS_STATE_TOPIC.format(mqtt_base_topic, lamp),
                actual_level.value,
                retain=True,
            )
            client.publish(
                MQTT_STATE_TOPIC.format(mqtt_base_topic, lamp),
                MQTT_PAYLOAD_ON if actual_level.value > 0 else MQTT_PAYLOAD_OFF,
                retain=True,
            )
        except DALIError as err:
            logger.error("While initializing lamp<%s>: %s", lamp, err)


def create_mqtt_client(
    driver_object, max_lamps, mqtt_server, mqtt_port, mqtt_base_topic, ha_prefix
):
    """Create MQTT client object, setup callbacks and connection to server."""
    logger.debug("Connecting to %s:%s", mqtt_server, mqtt_port)
    mqttc = mqtt.Client(
        client_id="dali2mqtt",
        userdata={"driver": driver_object, "base_topic": mqtt_base_topic},
    )
    mqttc.will_set(
        MQTT_DALI2MQTT_STATUS.format(mqtt_base_topic), MQTT_NOT_AVAILABLE, retain=True
    )
    mqttc.on_connect = lambda a, b, c, d: on_connect(a, b, c, d, max_lamps, ha_prefix)

    # Add message callbacks that will only trigger on a specific subscription match.
    mqttc.message_callback_add(
        MQTT_COMMAND_TOPIC.format(mqtt_base_topic, "+"), on_message_cmd
    )
    mqttc.message_callback_add(
        MQTT_BRIGHTNESS_COMMAND_TOPIC.format(mqtt_base_topic, "+"),
        on_message_brightness_cmd,
    )
    mqttc.on_message = on_message
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

    dali_driver = None
    logger.debug("Using <%s> driver", config.dali_driver)

    if config.dali_driver == HASSEB:
        from dali.driver.hasseb import SyncHassebDALIUSBDriver

        dali_driver = SyncHassebDALIUSBDriver()
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
            config.dali_lamps,
            *config.mqtt_conf,
            config.ha_discovery_prefix,
        )
        mqttc.loop_forever()
        if should_backoff:
            if retries == MAX_RETRIES:
                run = False
            time.sleep(delay())
            retries += 1  # TODO reset on successfull connection


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", help="configuration file", default=DEFAULT_CONFIG_FILE
    )
    parser.add_argument(
        "--mqtt-server", help="MQTT server", default=DEFAULT_MQTT_SERVER
    )
    parser.add_argument(
        "--mqtt-port", help="MQTT port", type=int, default=DEFAULT_MQTT_PORT
    )
    parser.add_argument(
        "--mqtt-base-topic", help="MQTT base topic", default=DEFAULT_MQTT_BASE_TOPIC
    )
    parser.add_argument(
        "--dali-driver",
        help="DALI device driver",
        choices=DALI_DRIVERS,
        default=DEFAULT_DALI_DRIVER,
    )
    parser.add_argument(
        "--dali-lamps", help="Number of lamps to scan", type=int, default=4
    )
    parser.add_argument(
        "--ha-discovery-prefix",
        help="HA discovery mqtt prefix",
        default=DEFAULT_HA_DISCOVERY_PREFIX,
    )
    parser.add_argument(
        "--log-level",
        help="Log level",
        choices=ALL_SUPPORTED_LOG_LEVELS,
        default=DEFAULT_LOG_LEVEL,
    )
    parser.add_argument(
        "--log-color",
        help="Coloring output",
        action="store_true",
        default=DEFAULT_LOG_COLOR,
    )

    args = parser.parse_args()

    main(args)
