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

from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler

HASSEB = "hasseb"
TRIDONIC = "tridonic"
DALI_SERVER = "dali_server"
DALI_DRIVERS = [HASSEB, TRIDONIC, DALI_SERVER]

DEFAULT_MQTT_BASE_TOPIC = "dali2mqtt"
DEFAULT_HA_DISCOVERY_PREFIX = "homeassistant"

MQTT_DALI2MQTT_STATUS = "{}/status"
MQTT_STATE_TOPIC = "{}/{}/light/status"
MQTT_COMMAND_TOPIC = "{}/{}/light/switch"
MQTT_BRIGHTNESS_STATE_TOPIC = "{}/{}/light/brightness/status"
MQTT_BRIGHTNESS_COMMAND_TOPIC = "{}/{}/light/brightness/set"
MQTT_PAYLOAD_ON = b"ON"
MQTT_PAYLOAD_OFF = b"OFF"
MQTT_AVAILABLE = "online"
MQTT_NOT_AVAILABLE = "offline"

HA_DISCOVERY_PREFIX = "{}/light/dali2mqtt_{}/config"


class ConfigFileSystemEventHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.mqqt_client = None


def load_config_file(path):
    with open(path, "r") as stream:
        logger.debug("Loading configuration from <%s>", path)
        return yaml.load(stream)


def gen_ha_config(light, mqtt_base_topic):
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
            "sw_version": "dali2mqtt 0.1",
            "model": "dali2mqtt",
            "manufacturer": "diogogomes@gmail.com",
        },
    }
    return json.dumps(json_config)


log_format = "%(asctime)s %(levelname)s: %(message)s"
logging.basicConfig(format=log_format, level=logging.INFO)
logger = logging.getLogger(__name__)


def dali_scan(driver_object, dali_bus_size=64, max_range=4):
    lamps = []
    for lamp in range(0, dali_bus_size):
        try:
            logging.debug("Search for Lamp {}".format(lamp))
            r = driver_object.send(gear.QueryControlGearPresent(address.Short(lamp)))
            if isinstance(r, YesNoResponse) and r.value:
                if len(lamps) >= max_range:
                    logger.warning(
                        "Script reaches maximum amount of lamps ({}) but on dali bus is connected more lamps".format(
                            max_range
                        )
                    )
                    logger.warning(
                        "Due this, lamp {} isn't handled by script".format(lamp)
                    )
                else:
                    lamps.append(lamp)
        except Exception as e:
            logger.warning("%s not present: %s", lamp, e)
    return lamps


def on_detect_changes_in_config(event, mqqt_client):
    logger.info(
        "Detected changes in configuration file {}, reloading".format(event.src_path)
    )
    mqqt_client.disconnect()


def on_message_cmd(mosq, data_object, msg):
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
            mosq.publish(
                MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                MQTT_PAYLOAD_OFF,
                retain=True,
            )
        except:
            logger.error("Failed to set light <%s> to %s", light, "OFF")


def on_message_brightness_cmd(mosq, data_object, msg):
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
        r = data_object["driver"].send(gear.DAPC(address.Short(light), level))
        if level == 0:
            # 0 in DALI is turn off with fade out
            mosq.publish(
                MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                MQTT_PAYLOAD_OFF,
                retain=True,
            )
        else:
            mosq.publish(
                MQTT_STATE_TOPIC.format(data_object["base_topic"], light),
                MQTT_PAYLOAD_ON,
                retain=True,
            )
        mosq.publish(
            MQTT_BRIGHTNESS_STATE_TOPIC.format(data_object["base_topic"], light),
            level,
            retain=True,
        )
    except ValueError as e:
        logger.error("Can't convert <%s> to interger 0..255: %s", level, e)


def on_message(mosq, data_object, msg):
    logger.error("Don't publish to %s", msg.topic)


def on_connect(
    client,
    data_object,
    flags,
    result,
    dali_bus_size,
    max_lamps=4,
    ha_prefix=DEFAULT_HA_DISCOVERY_PREFIX,
):
    mqqt_base_topic = data_object["base_topic"]
    driver_object = data_object["driver"]
    client.subscribe(
        [
            (MQTT_COMMAND_TOPIC.format(mqqt_base_topic, "+"), 0),
            (MQTT_BRIGHTNESS_COMMAND_TOPIC.format(mqqt_base_topic, "+"), 0),
        ]
    )
    client.publish(
        MQTT_DALI2MQTT_STATUS.format(mqqt_base_topic), MQTT_AVAILABLE, retain=True
    )
    lamps = dali_scan(driver_object, dali_bus_size, max_lamps)
    for lamp in lamps:
        try:
            r = driver_object.send(gear.QueryActualLevel(address.Short(lamp)))
            logger.debug("QueryActualLevel = %s", r.value)
            client.publish(
                HA_DISCOVERY_PREFIX.format(ha_prefix, lamp),
                gen_ha_config(lamp, mqqt_base_topic),
                retain=True,
            )
            client.publish(
                MQTT_BRIGHTNESS_STATE_TOPIC.format(mqqt_base_topic, lamp),
                r.value,
                retain=True,
            )
            client.publish(
                MQTT_STATE_TOPIC.format(mqqt_base_topic, lamp),
                MQTT_PAYLOAD_ON if r.value > 0 else MQTT_PAYLOAD_OFF,
                retain=True,
            )
            logger.info(
                "Lamp {} initialized, brightness level {}".format(lamp, r.value)
            )
        except Exception as e:
            logger.error("While initializing lamp<%s>: %s", lamp, e)


def create_mqtt_client(
    driver_object,
    dali_bus_size,
    max_lamps,
    mqtt_server,
    mqtt_port,
    mqqt_base_topic,
    ha_prefix,
):
    logger.debug("Connecting to %s:%s", mqtt_server, mqtt_port)
    mqttc = mqtt.Client(
        client_id="dali2mqtt",
        userdata={"driver": driver_object, "base_topic": mqqt_base_topic},
    )
    mqttc.will_set(
        MQTT_DALI2MQTT_STATUS.format(mqqt_base_topic), MQTT_NOT_AVAILABLE, retain=True
    )
    mqttc.on_connect = lambda a, b, c, d: on_connect(
        a, b, c, d, dali_bus_size, max_lamps, ha_prefix
    )

    # Add message callbacks that will only trigger on a specific subscription match.
    mqttc.message_callback_add(
        MQTT_COMMAND_TOPIC.format(mqqt_base_topic, "+"), on_message_cmd
    )
    mqttc.message_callback_add(
        MQTT_BRIGHTNESS_COMMAND_TOPIC.format(mqqt_base_topic, "+"),
        on_message_brightness_cmd,
    )
    mqttc.on_message = on_message
    mqttc.connect(mqtt_server, mqtt_port, 60)
    return mqttc


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="configuration file", default="config.ini")
    parser.add_argument("--mqtt-server", help="MQTT server", default="localhost")
    parser.add_argument("--mqtt-port", help="MQTT port", type=int, default=1883)
    parser.add_argument(
        "--mqtt-base-topic", help="MQTT base topic", default=DEFAULT_MQTT_BASE_TOPIC
    )
    parser.add_argument(
        "--dali-driver", help="DALI device driver", choices=DALI_DRIVERS, default=HASSEB
    )
    parser.add_argument(
        "--dali-bus-size",
        help="Maximum number of lamps on dali bus",
        type=int,
        default=64,
    )
    parser.add_argument(
        "--dali-lamps", help="Number of lamps to scan", type=int, default=4
    )
    parser.add_argument(
        "--ha-discover-prefix", help="HA discover mqtt prefix", default="homeassistant"
    )

    args = parser.parse_args()

    config = {
        "mqtt_server": args.mqtt_server,
        "mqtt_port": args.mqtt_port,
        "mqtt_base_topic": args.mqtt_base_topic,
        "dali_driver": args.dali_driver,
        "dali_bus_size": args.dali_bus_size,
        "dali_lamps": args.dali_lamps,
        "ha_discover_prefix": args.ha_discover_prefix,
    }

    exception_raised = False
    try:
        driver_object = None
        driver = args.dali_driver
        logger.debug("Using <%s> driver", driver)
        if driver == HASSEB:
            from dali.driver.hasseb import SyncHassebDALIUSBDriver

            driver_object = SyncHassebDALIUSBDriver()
        elif driver == TRIDONIC:
            from dali.driver.tridonic import SyncTridonicDALIUSBDriver

            driver_object = SyncTridonicDALIUSBDriver()
        elif driver == DALI_SERVER:
            from dali.driver.daliserver import DaliServer

            driver_object = DaliServer("localhost", 55825)

        watchdog_observer = Observer()
        watchdog_event_handler = ConfigFileSystemEventHandler()
        watchdog_event_handler.on_modified = lambda event: on_detect_changes_in_config(
            event, watchdog_event_handler.mqqt_client
        )
        watchdog_observer.schedule(watchdog_event_handler, args.config)
        watchdog_observer.start()

        while True:
            config = load_config_file(args.config)
            mqqtc = create_mqtt_client(
                driver_object,
                config["dali_bus_size"],
                config["dali_lamps"],
                config["mqtt_server"],
                config["mqtt_port"],
                config["mqtt_base_topic"],
                config["ha_discover_prefix"],
            )
            watchdog_event_handler.mqqt_client = mqqtc
            mqqtc.loop_forever()
    except FileNotFoundError as e:
        exception_raised = True
        logger.info("Configuration file %s created, please reload daemon", args.config)
    except KeyError as e:
        exception_raised = True
        missing_key = e.args[0]
        config[missing_key] = args.__dict__[missing_key]
        logger.info("Detected missing key, configuration file updated")
    finally:
        if exception_raised:
            try:
                with io.open(args.config, "w", encoding="utf8") as outfile:
                    yaml.dump(
                        config, outfile, default_flow_style=False, allow_unicode=True
                    )
            except Exception as err:
                logger.error(f"Could not save configuration: {err}")
