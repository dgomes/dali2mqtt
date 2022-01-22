"""Configuration Object."""
import traceback

import yaml
import logging

from .config import Config
from .consts import *

logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class DevicesNamesConfigLoadError(Exception):
    pass

class DevicesNamesConfig:
    _instance = None
    _done_setup = False

    _devices_names = {}

    def __new__(cls):
        if cls._instance is None:
            print('Creating the object')
            cls._instance = super(DevicesNamesConfig, cls).__new__(cls)
            # Put any initialization here.
        return cls._instance

    def setup(self):
        self._done_setup = True

        config = Config()
        self._path = config[CONF_DEVICES_NAMES_FILE]
        logger.setLevel(ALL_SUPPORTED_LOG_LEVELS[config[CONF_LOG_LEVEL]])

        # Load from file
        try:
            self.load_devices_names_file()
        except FileNotFoundError:
            logger.info("No device names config, creating new one")
            with open(self._path, "w"):
                pass


    def _did_setup(self):
        if not self._done_setup:
            raise SetupError("Class was not setup properly.")

    def load_devices_names_file(self):
        """Load configuration from yaml file."""
        self._did_setup()
        try:
            with open(self._path, "r") as infile:
                logger.debug("Loading devices names from <%s>", self._path)
                self._devices_names = yaml.safe_load(infile) or {}
        except yaml.YAMLError as error:
            logger.error("In devices file %s: %s", self._path, error)
            raise DevicesNamesConfigLoadError()
        except Exception as err:
            logger.warning("Could not load device names config: %s", err)

    def save_devices_names_file(self, all_lamps):
        self._did_setup()
        self._devices_names = {}
        try:
            for lamp_object in all_lamps:
                self._devices_names[lamp_object.device_name] = {
                    "friendly_name": str(lamp_object.friendly_name)
                }

            with open(self._path, "w") as outfile:
                yaml.dump(
                    self._devices_names,
                    outfile,
                    default_flow_style=False,
                    allow_unicode=True,
                )
        except Exception as err:
            logger.error("Could not save device names config: %s", err)
            print(traceback.format_exc())

    def is_devices_file_empty(self):
        self._did_setup()
        return len(self._devices_names) == 0

    def get_friendly_name(self, short_address_value):
        self._did_setup()
        try:
            friendly_name = f"Group {self._devices_names[short_address_value]['friendly_name']}"
        except KeyError:
            friendly_name = short_address_value
        return friendly_name
