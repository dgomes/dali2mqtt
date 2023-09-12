"""Configuration Object."""
import logging

import voluptuous as vol
import yaml
from dali2mqtt.consts import (
    ALL_SUPPORTED_LOG_LEVELS,
    CONF_CONFIG,
    CONF_DALI_DRIVER,
    CONF_DEVICES_NAMES_FILE,
    CONF_HA_DISCOVERY_PREFIX,
    CONF_LOG_COLOR,
    CONF_LOG_LEVEL,
    CONF_MQTT_BASE_TOPIC,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_SERVER,
    CONF_MQTT_USERNAME,
    DALI_DRIVERS,
    DEFAULT_DALI_DRIVER,
    DEFAULT_DEVICES_NAMES_FILE,
    DEFAULT_HA_DISCOVERY_PREFIX,
    DEFAULT_LOG_COLOR,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MQTT_BASE_TOPIC,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_SERVER,
    LOG_FORMAT,
)
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

CONF_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MQTT_SERVER, default=DEFAULT_MQTT_SERVER): str,
        vol.Optional(CONF_MQTT_PORT, default=DEFAULT_MQTT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Optional(CONF_MQTT_BASE_TOPIC, default=DEFAULT_MQTT_BASE_TOPIC): str,
        vol.Required(CONF_DALI_DRIVER, default=DEFAULT_DALI_DRIVER): vol.In(
            DALI_DRIVERS
        ),
        vol.Optional(
            CONF_HA_DISCOVERY_PREFIX, default=DEFAULT_HA_DISCOVERY_PREFIX
        ): str,
        vol.Optional(CONF_DEVICES_NAMES_FILE, default=DEFAULT_DEVICES_NAMES_FILE): str,
        vol.Optional(CONF_LOG_LEVEL, default=DEFAULT_LOG_LEVEL): vol.In(
            ALL_SUPPORTED_LOG_LEVELS
        ),
        vol.Optional(CONF_LOG_COLOR, default=DEFAULT_LOG_COLOR): bool,
    },
    extra=True,
)

logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class Config:
    """Configuration representation."""

    def __init__(self, args, callback=None):
        """Initialize configuration."""
        self._watchdog_observer = None
        self._path = args.config
        self._callback = callback
        self._config = {}

        # Load from file
        try:
            self.load_config_file()
        except FileNotFoundError:
            logger.info("No configuration file, creating a new one")
            self._config = CONF_SCHEMA({})

        # Overwrite with command line arguments
        args_keys = vars(args)
        for key in args_keys:
            if self._config.get(key) != args_keys[key]:
                self._config[key] = args_keys[key]

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
                configuration = yaml.safe_load(infile)
                if not configuration:
                    logger.warning(
                        "Could not load a configuration from %s, creating a new one",
                        self._path,
                    )
                    configuration = {}
                self._config = CONF_SCHEMA(configuration)
                if self._callback:
                    self._callback()
            except AttributeError:
                # No callback configured
                pass
            except vol.MultipleInvalid as error:
                logger.error("In configuration file %s: %s", self._path, error)
                quit(1)

    def save_config_file(self):
        """Save configuration back to yaml file."""
        try:
            cfg = self._config.pop(CONF_CONFIG)  # temporary displace config file
            with open(self._path, "w", encoding="utf8") as outfile:
                yaml.dump(
                    self._config, outfile, default_flow_style=False, allow_unicode=True
                )
        except Exception as err:
            logger.error("Could not save configuration: %s", err)
        finally:
            self._config[CONF_CONFIG] = cfg  # restore

    def __del__(self):
        """Release watchdog."""
        if self._watchdog_observer:
            self._watchdog_observer.stop()
            self._watchdog_observer.join()
        if self._config != {}:
            self.save_config_file()

    def __repr__(self):
        """Retrieve dictionary of the config file."""
        return self._config

    @property
    def mqtt_conf(self):
        """MQTT Settings."""
        return (
            self._config[CONF_MQTT_SERVER],
            self._config[CONF_MQTT_PORT],
            self._config.get(CONF_MQTT_USERNAME),
            self._config.get(CONF_MQTT_PASSWORD),
            self._config[CONF_MQTT_BASE_TOPIC],
        )

    @property
    def dali_driver(self):
        """DALI driver configured."""
        return self._config[CONF_DALI_DRIVER]

    @property
    def ha_discovery_prefix(self):
        """Home Assistant discovery prefix."""
        return self._config[CONF_HA_DISCOVERY_PREFIX]

    @property
    def log_level(self):
        """Level to be used for logging."""
        return self._config[CONF_LOG_LEVEL]

    @property
    def log_color(self):
        """Color to be used for logs."""
        return self._config[CONF_LOG_COLOR]

    @property
    def devices_names_file(self):
        """Return filename containing devices names."""
        return self._config[CONF_DEVICES_NAMES_FILE]
