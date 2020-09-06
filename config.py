"""Configuration Object."""
import logging
import yaml
import voluptuous as vol
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

from consts import RESET_COLOR

log_format = "%(asctime)s %(levelname)s: %(message)s{}".format(RESET_COLOR)
logging.basicConfig(format=log_format)
logger = logging.getLogger(__name__)

from consts import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_SERVER,
    DEFAULT_HA_DISCOVERY_PREFIX,
    DEFAULT_MQTT_BASE_TOPIC,
        DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_COLOR,
    DEFAULT_DALI_DRIVER,
    DEFAULT_DALI_LAMPS,
    DALI_DRIVERS,
    ALL_SUPPORTED_LOG_LEVELS,
)

CONF_MQTT_SERVER = "mqtt_server"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_BASE_TOPIC = "mqtt_base_topic"
CONF_DALI_DRIVER = "dali_driver"
CONF_DALI_LAMPS = "dali_lamps"
CONF_HA_DISCOVERY_PREFIX = "ha_discovery_prefix"
CONF_LOG_LEVEL = "log_level"
CONF_LOG_COLOR = "log_color"

CONF_SCHEMA = vol.Schema ({
    vol.Required(CONF_MQTT_SERVER, default=DEFAULT_MQTT_SERVER): str,
    vol.Optional(CONF_MQTT_PORT, default=DEFAULT_MQTT_PORT): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
    vol.Optional(CONF_MQTT_BASE_TOPIC, default=DEFAULT_MQTT_BASE_TOPIC): str,
    vol.Required(CONF_DALI_DRIVER, default=DEFAULT_DALI_DRIVER): vol.In(DALI_DRIVERS),
    vol.Optional(CONF_DALI_LAMPS, default=DEFAULT_DALI_LAMPS): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)), 
    vol.Optional(CONF_HA_DISCOVERY_PREFIX, default=DEFAULT_HA_DISCOVERY_PREFIX): str,
    vol.Optional(CONF_LOG_LEVEL, default=DEFAULT_LOG_LEVEL): vol.In(ALL_SUPPORTED_LOG_LEVELS),
    vol.Optional(CONF_LOG_COLOR, default=DEFAULT_LOG_COLOR): bool,
})

class Config:
    def __init__(self, args, callback=None):
        self._watchdog_observer = None
        self._path = args.config
        self._callback = callback
        self._config = {}

        # Load from file
        self.load_config_file()

        # Overwrite with command line arguments
        if self._config.get(CONF_MQTT_SERVER) != args.mqtt_server:
            self._config[CONF_MQTT_SERVER] = args.mqtt_server
        if self._config.get(CONF_MQTT_PORT) != args.mqtt_port:
            self._config[CONF_MQTT_PORT] = args.mqtt_port
        if self._config.get(CONF_MQTT_BASE_TOPIC) != args.mqtt_base_topic:
            self._config[CONF_MQTT_BASE_TOPIC] = args.mqtt_base_topic
        if self._config.get(CONF_DALI_DRIVER) != args.dali_driver:
            self._config[CONF_DALI_DRIVER] = args.dali_driver
        if self._config.get(CONF_DALI_LAMPS) != args.dali_lamps:
            self._config[CONF_DALI_LAMPS] = args.dali_lamps
        if self._config.get(CONF_HA_DISCOVERY_PREFIX) != args.ha_discovery_prefix:
            self._config[CONF_HA_DISCOVERY_PREFIX] = args.ha_discovery_prefix
        if self._config.get(CONF_LOG_LEVEL) != args.log_level:
            self._config[CONF_LOG_LEVEL] = args.log_level
        if self._config.get(CONF_LOG_COLOR) != args.log_color:
            self._config[CONF_LOG_COLOR] = args.log_color

        self.save_config_file()

        self._watchdog_observer = Observer()
        watchdog_event_handler = FileSystemEventHandler()
        watchdog_event_handler.on_modified = lambda event: self.load_config_file()
        self._watchdog_observer.schedule(watchdog_event_handler, self._path)
        self._watchdog_observer.start()      

    def load_config_file(self):
        """Load configuration from yaml file."""
        with open(self._path, "r") as infile:
            logger.debug("Loading configuration from <%s>", self._path)
            try:
                configuration = yaml.load(infile)
                if not configuration:
                    logger.warning("Could not load a configuration from %s, creating a new one", self._path)
                    configuration = {}
                self._config = CONF_SCHEMA(configuration)
                self._callback()
            except AttributeError:
                #No callback configured 
                pass
            except vol.MultipleInvalid as error:
                logger.error("In configuration file %s: %s", self._path, error)
                quit(1)
    
    def save_config_file(self):
        """Save configuration back to yaml file."""
        try:
            with open(self._path, "w", encoding="utf8") as outfile:
                yaml.dump(
                    self._config, outfile, default_flow_style=False, allow_unicode=True
                )
        except Exception as err:
            logger.error("Could not save configuration: %s", err)

    def __del__(self):
        """Release watchdog."""
        if self._watchdog_observer:
            self._watchdog_observer.stop()
            self._watchdog_observer.join()
        if self._config != {}:
            self.save_config_file()

    def __repr__(self):
        return self._config

    @property
    def mqtt_conf(self):
        return self._config[CONF_MQTT_SERVER], self._config[CONF_MQTT_PORT], self._config[CONF_MQTT_BASE_TOPIC]

    @property
    def dali_driver(self):
        return self._config[CONF_DALI_DRIVER]

    @property
    def dali_lamps(self):
        return self._config[CONF_DALI_LAMPS]

    @property
    def ha_discovery_prefix(self):
        return self._config[CONF_HA_DISCOVERY_PREFIX]

    @property
    def log_level(self):
        return self._config[CONF_LOG_LEVEL]

    @property
    def log_color(self):
        return self._config[CONF_LOG_COLOR]
