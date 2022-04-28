"""Class to represent dali groups"""
import json
from statistics import median

import dali.gear.general as gear
from slugify import slugify

from .config import Config
from .consts import *

from .devicesnamesconfig import DevicesNamesConfig
from .functions import denormalize

logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class Group:
    def __init__(self, driver, mqtt, dali_group, lamps):
        self.config = Config()
        logger.setLevel(ALL_SUPPORTED_LOG_LEVELS[self.config[CONF_LOG_LEVEL]])

        self.driver = driver
        self.mqtt = mqtt
        self.dali_group = dali_group
        self.address = dali_group.group
        self.lamps = lamps

        self.level = round(median(x.level for x in self.lamps))
        self.min_levels = min(x.min_levels for x in self.lamps)
        self.max_level = max(x.max_level for x in self.lamps)

        self.friendly_name = DevicesNamesConfig().get_friendly_name(f"group_{self.address}")
        self.device_name = slugify(self.friendly_name)

        self.mqtt.publish(
            HA_DISCOVERY_PREFIX.format(self.config[CONF_HA_DISCOVERY_PREFIX], self.config[CONF_MQTT_BASE_TOPIC],
                                       self.device_name),
            self.gen_ha_config(),
            retain=True,
        )
        self.mqtt.publish(
            MQTT_BRIGHTNESS_STATE_TOPIC.format(self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
            self.level,
            retain=True,
        )

        self.mqtt.publish(
            MQTT_STATE_TOPIC.format(self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
            MQTT_PAYLOAD_ON if self.level > 0 else MQTT_PAYLOAD_OFF,
            retain=True,
        )
        logger.info(f"   - short address: {self.address}, actual brightness level: {self.level}")

    def __repr__(self):
        return f"GROUP A{self.address}"

    __str__ = __repr__

    def recalc_level(self):
        old = self.level
        if self.config[CONF_GROUP_MODE] == "median":
            self.level = round(median(x.level for x in self.lamps))
        elif self.config[CONF_GROUP_MODE] == "max":
            self.level = round(max(x.level for x in self.lamps))
        elif self.config[CONF_GROUP_MODE] == "min":
            self.level = round(min(x.level for x in self.lamps))
        elif self.config[CONF_GROUP_MODE] == "off":
            return
        else:
            raise RuntimeError(f"Invalid group mode: {self.config[CONF_GROUP_MODE]}")
        if old != self.level:
            self.mqtt.publish(
                MQTT_BRIGHTNESS_STATE_TOPIC.format(self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
                self.level,
                retain=True,
            )
            if old == 0 or self.level == 0:
                self.mqtt.publish(
                    MQTT_STATE_TOPIC.format(self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
                    MQTT_PAYLOAD_ON if self.level > 0 else MQTT_PAYLOAD_OFF,
                    retain=True,
                )

    def gen_ha_config(self):
        """Generate a automatic configuration for Home Assistant."""
        json_config = {
            "name": self.friendly_name,
            "unique_id": "DALI2MQTT_GROUP_{}".format(self.device_name),
            "state_topic": MQTT_STATE_TOPIC.format(self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
            "command_topic": MQTT_COMMAND_TOPIC.format(
                self.config[CONF_MQTT_BASE_TOPIC], self.device_name
            ),
            "payload_off": MQTT_PAYLOAD_OFF.decode("utf-8"),
            "brightness_state_topic": MQTT_BRIGHTNESS_STATE_TOPIC.format(
                self.config[CONF_MQTT_BASE_TOPIC], self.device_name
            ),
            "brightness_command_topic": MQTT_BRIGHTNESS_COMMAND_TOPIC.format(
                self.config[CONF_MQTT_BASE_TOPIC], self.device_name
            ),
            "brightness_scale": 255,
            "on_command_type": "brightness",
            "availability_topic": MQTT_DALI2MQTT_STATUS.format(self.config[CONF_MQTT_BASE_TOPIC]),
            "payload_available": MQTT_AVAILABLE,
            "payload_not_available": MQTT_NOT_AVAILABLE,
            "device": {
                "identifiers": f"{self.config[CONF_MQTT_BASE_TOPIC]}_A{self.address}",
                "via_device": self.config[CONF_MQTT_BASE_TOPIC],
                "name": f"DALI Group G{self.address}",
                "sw_version": f"dali2mqtt {VERSION}",
                "manufacturer": AUTHOR,
                "connections": [("DALI", f"A{self.address}")]
            },
        }
        return json.dumps(json_config)

    def setLevel(self, level):
        old = self.level
        self.level = level
        self._sendLevelDALI(level)

        affected_groups = set()
        for lamp in self.lamps:
            lamp.setLevel(level, False)
            affected_groups.update(lamp.groups)

        for _x in affected_groups:
            _x.recalc_level()

        self.mqtt.publish(
            MQTT_BRIGHTNESS_STATE_TOPIC.format(self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
            self.level,
            retain=True,
        )
        if old == 0 or level == 0:
            self.mqtt.publish(
                MQTT_STATE_TOPIC.format(self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
                MQTT_PAYLOAD_ON if self.level > 0 else MQTT_PAYLOAD_OFF,
                retain=True,
            )


    def _sendLevelDALI(self, level):
        if level != 0:
            level = denormalize(level, 0, 255, self.min_levels, self.max_level)
        self.driver.send(gear.DAPC(self.dali_group, level))
        logger.debug(f"Set group {self.friendly_name} brightness level to {self.level} ({level})")
