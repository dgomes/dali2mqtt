"""Tests for config."""

from dali2mqtt.config import Config
from unittest import mock

def test_load_config():
    args = mock.Mock()
    args.config = "tests/data/config.yaml"

    cfg = Config(args)

    assert cfg.mqtt_conf == ('localhost', 1883, None, None, 'dali2mqtt')
    assert cfg,dali_driver == "hasseb"
    assert cfg.ha_discovery_prefix == "homeassistant"
    assert cfg.log_level == "info"
    assert cfg.log_color == False
    assert cfg.devices_names_file == "devices.yaml"