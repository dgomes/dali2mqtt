"""Class to represent dali lamps"""
import json
from consts import (
    __author__,
    __version__,
    __email__,
    MQTT_STATE_TOPIC,
    MQTT_COMMAND_TOPIC,
    MQTT_PAYLOAD_OFF,
    MQTT_BRIGHTNESS_STATE_TOPIC,
    MQTT_BRIGHTNESS_COMMAND_TOPIC,
    MQTT_DALI2MQTT_STATUS,
    MQTT_AVAILABLE,
    MQTT_NOT_AVAILABLE,
)


class Lamp:
    def __init__(self, address, min_physical_level, min_level, max_level):
        self.address = address
        self.min_physical_level = min_physical_level
        self.min_level = min_level
        self.max_level = max_level
        pass

    def gen_ha_config(self, mqtt_base_topic):
        """Generate a automatic configuration for Home Assistant."""
        json_config = {
            "name": "DALI Light {}".format(self.address),
            "unique_id": "DALI2MQTT_LIGHT_{}".format(self.address),
            "state_topic": MQTT_STATE_TOPIC.format(mqtt_base_topic, self.address),
            "command_topic": MQTT_COMMAND_TOPIC.format(mqtt_base_topic, self.address),
            "payload_off": MQTT_PAYLOAD_OFF.decode("utf-8"),
            "brightness_state_topic": MQTT_BRIGHTNESS_STATE_TOPIC.format(
                mqtt_base_topic, self.address
            ),
            "brightness_command_topic": MQTT_BRIGHTNESS_COMMAND_TOPIC.format(
                mqtt_base_topic, self.address
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
