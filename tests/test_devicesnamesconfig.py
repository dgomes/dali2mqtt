"""Tests for devices names config."""

from unittest import mock

import yaml
from dali.address import Group, Short

from dali2mqtt.devicesnamesconfig import DevicesNamesConfig
from dali2mqtt.lamp import Lamp


def test_save_skips_groups(tmp_path):
    """On first start the names file is written from all lamps, groups included."""
    driver = mock.Mock()
    driver.send = mock.Mock(return_value=mock.Mock(value=100))
    all_lamps = {
        "0": Lamp("debug", driver, "0", Short(0)),
        "group_1": Lamp("debug", driver, "group_1", Group(1)),
    }
    path = tmp_path / "devices.yaml"

    DevicesNamesConfig("debug", str(path)).save_devices_names_file(all_lamps)

    assert yaml.safe_load(path.read_text()) == {0: {"friendly_name": "0"}}
