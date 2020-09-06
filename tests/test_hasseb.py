"""Tests based on hasseb driver."""

from dali_mqtt_daemon import main
from unittest import mock
import pytest

from consts import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_MQTT_SERVER,
    DEFAULT_MQTT_PORT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_COLOR,
    DEFAULT_HA_DISCOVERY_PREFIX,
)

@pytest.fixture
def args():
    mock_args = mock.Mock()
    mock_args.config = DEFAULT_CONFIG_FILE
    mock_args.mqtt_server = DEFAULT_MQTT_SERVER
    mock_args.mqtt_port = DEFAULT_MQTT_PORT
    mock_args.ha_discovery_prefix = DEFAULT_HA_DISCOVERY_PREFIX
    mock_args.dali_driver = "dummy"
    mock_args.log_level = DEFAULT_LOG_LEVEL
    mock_args.log_color = DEFAULT_LOG_COLOR
    return mock_args

@pytest.fixture
def config():
    return {"config": "config.yaml",
            "dali_driver": "hasseb",
            "dali_lamps": 2,
            "mqtt_server": "localhost",
            "mqtt_port": 1883,
            "mqtt_base_topic": "dali2mqtt",
            "ha_discovery_prefix": "homeassistant",
            "log_level": "info",
            "log_color": False,
    }

def test_main(args, config):
    with mock.patch('dali_mqtt_daemon.create_mqtt_client', return_value=mock.Mock()) as mock_mqtt_client:
        with mock.patch("dali_mqtt_daemon.delay", return_value=0):
            with mock.patch('yaml.load', return_value={}) as mock_config_file:
                mock_mqtt_client.loop_forever = mock.Mock()
                main(args)
                mock_config_file.assert_called()
                assert mock_mqtt_client.call_count == 11