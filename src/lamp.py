"""Class to represent dali lamps"""
import json
import dali.gear.general as gear
from slugify import slugify

from .config import Config
from .consts import *

from .devicesnamesconfig import DevicesNamesConfig
from .functions import denormalize

logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class Lamp:
    def __init__(self, driver, mqtt, dali_lamp):
        self.config = Config()
        logger.setLevel(ALL_SUPPORTED_LOG_LEVELS[self.config[CONF_LOG_LEVEL]])

        self.driver = driver
        self.mqtt = mqtt
        self.dali_lamp = dali_lamp
        self.address = dali_lamp.address

        self.groups = []

        self.min_physical_level = self.driver.send(gear.QueryPhysicalMinimum(self.dali_lamp)).value
        self.min_level = self.driver.send(gear.QueryMinLevel(self.dali_lamp)).value
        self.min_levels = max(self.min_physical_level, self.min_level)
        self.max_level = self.driver.send(gear.QueryMaxLevel(self.dali_lamp)).value

        self.friendly_name = DevicesNamesConfig().get_friendly_name(f"lamp_{self.address}")
        self.device_name = slugify(self.friendly_name)

        self._getLevelDALI()

        self.mqtt.publish(
            HA_DISCOVERY_PREFIX.format(self.config[CONF_HA_DISCOVERY_PREFIX], self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
            self.gen_ha_config(),
            retain=True,
        )
        self.mqtt.publish(
            MQTT_BRIGHTNESS_STATE_TOPIC.format(self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
            self.level,
            retain=False,
        )
        self.mqtt.publish(
            MQTT_STATE_TOPIC.format(self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
            MQTT_PAYLOAD_ON if self.level > 0 else MQTT_PAYLOAD_OFF,
            retain=False,
        )
        logger.info(
            "   - short address: %d, actual brightness level: %d (minimum: %d, max: %d, physical minimum: %d)",
            self.address,
            self.level,
            self.min_level,
            self.max_level,
            self.min_physical_level,
        )

    def __repr__(self):
        return f"LAMP A{self.address}"

    __str__ = __repr__

    def addGroup(self, group):
        self.groups.append(group)

    def gen_ha_config(self):
        """Generate a automatic configuration for Home Assistant."""
        json_config = {
            "name": self.friendly_name,
            "unique_id": "DALI2MQTT_LIGHT_{}".format(self.device_name),
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
                "name": f"DALI Light A{self.address}",
                "sw_version": f"dali2mqtt {VERSION}",
                "manufacturer": AUTHOR,
                "connections": [("DALI", f"A{self.address}")]
            },
        }
        return json.dumps(json_config)

    def setLevel(self, level, dali=True):
        if self.level == level:
            return
        old = self.level
        self.level = level

        if dali:
            for _x in self.groups:
                _x.recalc_level()
            self._sendLevelDALI(level)

        self.mqtt.publish(
            MQTT_BRIGHTNESS_STATE_TOPIC.format(self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
            self.level,
            retain=False,
        )
        if old == 0 or level == 0:
            self.mqtt.publish(
                MQTT_STATE_TOPIC.format(self.config[CONF_MQTT_BASE_TOPIC], self.device_name),
                MQTT_PAYLOAD_ON if self.level > 0 else MQTT_PAYLOAD_OFF,
                retain=False,
            )

    def _sendLevelDALI(self, level):
        level = denormalize(level, 0, 255, self.min_levels, self.max_level)
        self.driver.send(gear.DAPC(self.dali_lamp, level))
        logger.debug(f"Set lamp {self.friendly_name} brightness level to {self.level} ({level})")

    def _getLevelDALI(self):
        level = self.driver.send(gear.QueryActualLevel(self.dali_lamp)).value
        if level == 0:
            self.level = 0
        else:
            self.level = denormalize(level, self.min_levels, self.max_level, 0, 255)
        logger.debug(f"Get lamp {self.friendly_name} brightness level {self.level} ({level})")
