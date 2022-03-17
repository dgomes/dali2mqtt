"""Configuration Object."""
import yaml
import logging

from consts import LOG_FORMAT, ALL_SUPPORTED_LOG_LEVELS

logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class DevicesNamesConfigLoadError(Exception):
    pass


class DevicesNamesConfig:
    def __init__(self, log_level, filename):
        self._path = filename
        self._devices_names = {}

        logger.setLevel(ALL_SUPPORTED_LOG_LEVELS[log_level])
        # Load from file
        try:
            self.load_devices_names_file()
        except FileNotFoundError:
            logger.info("No device names config, creating new one")
            with open(self._path, "w"):
                pass

    def load_devices_names_file(self):
        """Load configuration from yaml file."""
        try:
            with open(self._path, "r") as infile:
                logger.debug("Loading devices names from <%s>", self._path)
                self._devices_names = yaml.safe_load(infile) or {}
        except yaml.YAMLError as error:
            logger.error("In devices file %s: %s", self._path, error)
            raise DevicesNamesConfigLoadError()
        except Exception as err:
            logger.error("Could not load device names config: %s", err)

    def save_devices_names_file(self, all_lamps):
        self._devices_names = {}
        for lamp_object in all_lamps.values():
            self._devices_names[lamp_object.short_address.address] = {
                "friendly_name": str(lamp_object.short_address.address)
            }
        try:
            with open(self._path, "w") as outfile:
                yaml.dump(
                    self._devices_names,
                    outfile,
                    default_flow_style=False,
                    allow_unicode=True,
                )
        except Exception as err:
            logger.error("Could not save device names config: %s", err)

    def is_devices_file_empty(self):
        return len(self._devices_names) == 0

    def get_friendly_name(self, short_address_value) -> str:
        friendly_name = None
        try:
            friendly_name = self._devices_names[short_address_value]["friendly_name"]
        except KeyError:
            friendly_name = f"{short_address_value}"
        return friendly_name
