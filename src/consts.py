import logging
import voluptuous as vol

"""Constants common the various modules."""
AUTHOR = "Diogo Gomes & TobsA"
VERSION = "0.1.0"

HASSEB = "hasseb"
MIN_HASSEB_FIRMWARE_VERSION = 2.3
TRIDONIC = "tridonic"
DALI_SERVER = "dali_server"
DALI_DRIVERS = [HASSEB, TRIDONIC, DALI_SERVER, "dummy"]

CONF_CONFIG = "config"
CONF_CONFIG_EXAMPLE = "config_example"
CONF_DEVICES_NAMES_FILE = "devices_names"
CONF_MQTT_SERVER = "mqtt_server"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"
CONF_MQTT_BASE_TOPIC = "mqtt_base_topic"
CONF_DALI_DRIVER = "dali_driver"
CONF_DALI_LAMPS = "dali_lamps"
CONF_HA_DISCOVERY_PREFIX = "ha_discovery_prefix"
CONF_LOG_LEVEL = "log_level"
CONF_LOG_COLOR = "log_color"
CONF_GROUP_MODE = "group_mode"

DEFAULT_CONFIG_FILE = "config.yaml"
DEFAULT_DEVICES_NAMES_FILE = "devices.yaml"
DEFAULT_MQTT_SERVER = "localhost"
DEFAULT_MQTT_PORT = "1883"
DEFAULT_MQTT_USERNAME = ""
DEFAULT_MQTT_PASSWORD = ""
DEFAULT_MQTT_BASE_TOPIC = "dali2mqtt"
DEFAULT_DALI_DRIVER = "hasseb"
DEFAULT_DALI_LAMPS = 64
DEFAULT_HA_DISCOVERY_PREFIX = "homeassistant"
DEFAULT_LOG_LEVEL = "info"
DEFAULT_LOG_COLOR = False
DEFAULT_GROUP_MODE = "median"

ALL_SUPPORTED_LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}

ALL_SUPPORTED_GROUP_MODES = ["median", "max", "min", "off"]

RESET_COLOR = "\x1b[0m"
RED_COLOR = "\x1b[31;21m"
YELLOW_COLOR = "\x1b[33;21m"
LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s{}".format(RESET_COLOR)

CONF_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MQTT_SERVER, default=DEFAULT_MQTT_SERVER): str,
        vol.Optional(CONF_MQTT_PORT, default=DEFAULT_MQTT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Optional(CONF_MQTT_USERNAME, default=DEFAULT_MQTT_USERNAME): str,
        vol.Optional(CONF_MQTT_PASSWORD, default=DEFAULT_MQTT_PASSWORD): str,
        vol.Optional(CONF_MQTT_BASE_TOPIC, default=DEFAULT_MQTT_BASE_TOPIC): str,

        vol.Required(CONF_DALI_DRIVER, default=DEFAULT_DALI_DRIVER): vol.In(
            DALI_DRIVERS
        ),
        vol.Optional(CONF_DALI_LAMPS, default=DEFAULT_DALI_LAMPS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=64)
        ),
        vol.Optional(
            CONF_HA_DISCOVERY_PREFIX, default=DEFAULT_HA_DISCOVERY_PREFIX
        ): str,
        vol.Optional(CONF_DEVICES_NAMES_FILE, default=DEFAULT_DEVICES_NAMES_FILE): str,
        vol.Optional(CONF_LOG_LEVEL, default=DEFAULT_LOG_LEVEL): vol.In(
            ALL_SUPPORTED_LOG_LEVELS
        ),
        vol.Optional(CONF_LOG_COLOR, default=DEFAULT_LOG_COLOR): bool,
        vol.Optional(CONF_GROUP_MODE, default=DEFAULT_GROUP_MODE): vol.In(
            ALL_SUPPORTED_GROUP_MODES
        ),
    },
    extra=False,
)

MQTT_DALI2MQTT_STATUS = "{}/status"
MQTT_STATE_TOPIC = "{}/{}/status"
MQTT_COMMAND_TOPIC = "{}/{}/set"
MQTT_BRIGHTNESS_STATE_TOPIC = "{}/{}/brightness/status"
MQTT_BRIGHTNESS_COMMAND_TOPIC = "{}/{}/brightness/set"
MQTT_SCAN_LAMPS_COMMAND_TOPIC = "{}/scan"
MQTT_POLL_LAMPS_COMMAND_TOPIC = "{}/poll"
MQTT_PAYLOAD_ON = b"ON"
MQTT_PAYLOAD_OFF = b"OFF"
MQTT_AVAILABLE = "online"
MQTT_NOT_AVAILABLE = "offline"

HA_DISCOVERY_PREFIX = "{}/light/{}/{}/config"


class SetupError(Exception):
    pass