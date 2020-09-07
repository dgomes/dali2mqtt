import logging

"""Constants common the various modules."""
HASSEB = "hasseb"
TRIDONIC = "tridonic"
DALI_SERVER = "dali_server"
DALI_DRIVERS = [HASSEB, TRIDONIC, DALI_SERVER, "dummy"]

CONF_CONFIG = "config"
CONF_MQTT_SERVER = "mqtt_server"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_BASE_TOPIC = "mqtt_base_topic"
CONF_DALI_DRIVER = "dali_driver"
CONF_DALI_LAMPS = "dali_lamps"
CONF_HA_DISCOVERY_PREFIX = "ha_discovery_prefix"
CONF_LOG_LEVEL = "log_level"
CONF_LOG_COLOR = "log_color"

DEFAULT_CONFIG_FILE = "config.yaml"
DEFAULT_MQTT_SERVER = "localhost"
DEFAULT_MQTT_PORT = "1883"
DEFAULT_MQTT_BASE_TOPIC = "dali2mqtt"
DEFAULT_HA_DISCOVERY_PREFIX = "homeassistant"
DEFAULT_DALI_DRIVER = "hasseb"
DEFAULT_LOG_LEVEL = "info"
DEFAULT_LOG_COLOR = False

MQTT_DALI2MQTT_STATUS = "{}/status"
MQTT_STATE_TOPIC = "{}/{}/light/status"
MQTT_COMMAND_TOPIC = "{}/{}/light/switch"
MQTT_BRIGHTNESS_STATE_TOPIC = "{}/{}/light/brightness/status"
MQTT_BRIGHTNESS_COMMAND_TOPIC = "{}/{}/light/brightness/set"
MQTT_BRIGHTNESS_MAX_LEVEL_TOPIC = "{}/{}/max_level"
MQTT_BRIGHTNESS_MIN_LEVEL_TOPIC = "{}/{}/min_level"
MQTT_BRIGHTNESS_PHYSICAL_MINIMUM_LEVEL_TOPIC = "{}/{}/physical_minimum"
MQTT_PAYLOAD_ON = b"ON"
MQTT_PAYLOAD_OFF = b"OFF"
MQTT_AVAILABLE = "online"
MQTT_NOT_AVAILABLE = "offline"

HA_DISCOVERY_PREFIX = "{}/light/dali2mqtt_{}/config"

MIN_HASSEB_FIRMWARE_VERSION = 2.3
MIN_BACKOFF_TIME = 2
MAX_RETRIES = 10

ALL_SUPPORTED_LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


RESET_COLOR = "\x1b[0m"
RED_COLOR = "\x1b[31;21m"
YELLOW_COLOR = "\x1b[33;21m"
