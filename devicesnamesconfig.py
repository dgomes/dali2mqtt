"""Configuration Object."""
import yaml

from consts import logger


class DevicesNamesConfigLoadError(Exception):
    pass


class DevicesNamesConfig:
    def __init__(self, filename):
        self._path = filename
        self._devices_names = {}
        # Load from file
        try:
            self.load_devices_names_file()
        except FileNotFoundError:
            logger.info("No device names config, creating new one")
            with open(self._path, "w"):
                pass

    def load_devices_names_file(self):
        """Load configuration from yaml file."""
        with open(self._path, "r") as infile:
            logger.debug("Loading devices names from <%s>", self._path)
            try:
                self._devices_names = yaml.safe_load(infile) or {}
            except yaml.YAMLError as error:
                logger.error("In devices file %s: %s", self._path, error)
                raise DevicesNamesConfigLoadError()

    def save_devices_names_file(self, all_lamps):
        self._devices_names = {}
        for lamp_object in all_lamps.values():
            self._devices_names[lamp_object.short_address.address] = {
                "friendly_name": str(lamp_object.short_address.address)
            }
        with open(self._path, "w") as outfile:
            yaml.dump(
                self._devices_names,
                outfile,
                default_flow_style=False,
                allow_unicode=True,
            )

    def is_devices_file_empty(self):
        return len(self._devices_names) == 0

    def get_friendly_name(self, short_address_value):
        friendly_name = None
        try:
            friendly_name = self._devices_names[short_address_value]["friendly_name"]
        except KeyError:
            friendly_name = short_address_value
        return friendly_name
