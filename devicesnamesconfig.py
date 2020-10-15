"""Configuration Object."""
import yaml

from consts import logger


class DevicesNamesConfig:
    def __init__(self):
        self._path = "devices.yaml"
        self._devices_names = {}
        # Load from file
        try:
            self.load_devices_names_file()
        except FileNotFoundError:
            logger.info("No device names config, creating new one")
            open(self._path, "w")
            self._devices_names = {}

    def load_devices_names_file(self):
        """Load configuration from yaml file."""
        with open(self._path, "r") as infile:
            logger.debug("Loading devices names from <%s>", self._path)
            try:
                self._devices_names = yaml.safe_load(infile)
            except vol.MultipleInvalid as error:
                logger.error("In configuration file %s: %s", self._path, error)
                quit(1)

    @property
    def devices_names(self):
        return self._devices_names
