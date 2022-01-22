"""Configuration Object."""
import logging
import yaml
import voluptuous as vol
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

from .consts import *

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
    },
    extra=True,
)

logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)




class Config:
    _instance = None
    _done_setup = False
    _watchdog_observer = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            print('Creating the object')
            cls._instance = super(Config, cls).__new__(cls)
            # Put any initialization here.
        return cls._instance


    def setup(self, args, callback=None):
        self._done_setup = True
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

    def _did_setup(self):
        if not self._done_setup:
            raise SetupError("Class was not setup properly.")

    def load_config_file(self):
        """Load configuration from yaml file."""
        self._did_setup()
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
                self._callback()
            except AttributeError:
                # No callback configured
                pass
            except vol.MultipleInvalid as error:
                logger.error("In configuration file %s: %s", self._path, error)
                quit(1)

    def save_config_file(self):
        """Save configuration back to yaml file."""
        self._did_setup()
        try:
            with open(self._path, "w", encoding="utf8") as outfile:
                cfg = self._config.pop(CONF_CONFIG)  # temporary displace config file
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
        self._did_setup()
        return self._config

    def __getitem__(self, item):
        self._did_setup()
        if item not in self._config:
            raise IndexError(f"Value {item} not in config")
        else:
            return self._config[item]

    def __contains__(self, item):
        self._did_setup()
        return item not in self._config

    @property
    def mqtt_conf(self):
        self._did_setup()
        return (
            self._config[CONF_MQTT_SERVER],
            self._config[CONF_MQTT_PORT],
            self._config.get(CONF_MQTT_USERNAME, DEFAULT_MQTT_USERNAME),
            self._config.get(CONF_MQTT_PASSWORD, DEFAULT_MQTT_PASSWORD),
            self._config[CONF_MQTT_BASE_TOPIC],
        )

