"""Class to represent dali lamps"""
import json
import logging
import dali.gear.general as gear
from slugify import slugify

from consts import (
    __author__,
    __version__,
    __email__,
    logger,
    MQTT_STATE_TOPIC,
    MQTT_COMMAND_TOPIC,
    MQTT_PAYLOAD_OFF,
    MQTT_BRIGHTNESS_STATE_TOPIC,
    MQTT_BRIGHTNESS_COMMAND_TOPIC,
    MQTT_DALI2MQTT_STATUS,
    MQTT_AVAILABLE,
    MQTT_NOT_AVAILABLE,
    RESET_COLOR,
)


class Lamp:
    def __init__(
        self,
        driver,
        friendly_name,
        short_address,
        min_physical_level,
        min_level,
        level,
        max_level,
    ):
        self.driver = driver
        self.short_address = short_address
        self.friendly_name = friendly_name
        self.device_name = slugify(friendly_name)
        self.min_physical_level = min_physical_level
        self.min_level = min_level
        self.max_level = max_level
        self.level = level
        pass

    def gen_ha_config(self, mqtt_base_topic):
        """Generate a automatic configuration for Home Assistant."""
        json_config = {
            "name": self.friendly_name,
            "unique_id": "DALI2MQTT_LIGHT_{}".format(self.device_name),
            "state_topic": MQTT_STATE_TOPIC.format(mqtt_base_topic, self.device_name),
            "command_topic": MQTT_COMMAND_TOPIC.format(
                mqtt_base_topic, self.device_name
            ),
            "payload_off": MQTT_PAYLOAD_OFF.decode("utf-8"),
            "brightness_state_topic": MQTT_BRIGHTNESS_STATE_TOPIC.format(
                mqtt_base_topic, self.device_name
            ),
            "brightness_command_topic": MQTT_BRIGHTNESS_COMMAND_TOPIC.format(
                mqtt_base_topic, self.device_name
            ),
            "brightness_scale": self.max_level,
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

    @property
    def level(self):
        return self.__level

    @level.setter
    def level(self, value):
        if not self.min_level <= value <= self.max_level and value != 0:
            raise ValueError
        self.__level = value
        self.driver.send(gear.DAPC(self.short_address, self.level))
        logger.debug(
            "Set lamp <%s> brightness level to %s", self.friendly_name, self.level
        )
