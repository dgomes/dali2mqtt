import logging

"""Constants common the various modules."""
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

MQTT_BRIGHTNESS_MAX_LEVEL_TOPIC = "{}/{}/light/brightness/max_level"
MQTT_BRIGHTNESS_MIN_LEVEL_TOPIC = "{}/{}/light/brightness/min_level"
MQTT_BRIGHTNESS_MIN_PHYSICAL_LEVEL_TOPIC = "{}/{}/light/brightness/min_physical_level"


HA_DISCOVERY_PREFIX = "{}/light/dali2mqtt_{}/config"

MIN_BACKOFF_TIME = 2
MAX_RETRIES = 10

ALL_SUPPORTED_LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}
