"""Configuration Object."""
from .consts import *

logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class Config:
    _instance = None
    _done_setup = False
    _config = None

    def __new__(cls):
        if cls._instance is None:
            print('Creating the object')
            cls._instance = super(Config, cls).__new__(cls)
            # Put any initialization here.
        return cls._instance

    def setup(self, config):
        self._done_setup = True
        self._config = CONF_SCHEMA(config)

    def _did_setup(self):
        if not self._done_setup:
            raise SetupError("Class was not setup properly.")

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
