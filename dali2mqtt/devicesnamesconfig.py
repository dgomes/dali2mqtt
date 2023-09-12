"""Configuration Object."""
import logging

import yaml
from dali2mqtt.consts import ALL_SUPPORTED_LOG_LEVELS, LOG_FORMAT

logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class DevicesNamesConfigLoadError(Exception):
    """Exception class for DevicesNamesConfig."""

    pass


class DevicesNamesConfig:
    """Devices Names Configuration."""

    def __init__(self, log_level, filename):
        """Initialize devices names config."""
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
        except Exception:
            logger.error(
                "Could not load device names config <%s>, a new one will be created after successfull start",
                self._path,
            )

    def save_devices_names_file(self, all_lamps):
        """Save configuration back to yaml file."""
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

    def is_devices_file_empty(self) -> bool:
        """Check if we have any device configured."""
        return len(self._devices_names) == 0

    def get_friendly_name(self, short_address_value) -> str:
        """Retrieve friendly_name."""
        if short_address_value in self._devices_names:
            return self._devices_names[short_address_value].get(
                "friendly_name", f"{short_address_value}"
            )
        return str(short_address_value)
