"""Tests based on hasseb driver."""

from dali_mqtt_daemon import main
from unittest import mock
import pytest

@pytest.fixture
def config():
    return {"config": "config.yaml",
            "dali_driver": "DUMMY",
            "dali_lamps": 2,
            "mqtt_server": "localhost",
            "mqtt_port": 1883,
            "mqtt_base_topic": "dali2mqtt",
            "ha_discover_prefix": "homeassistant",
    }

@mock.patch("time.sleep", return_value=0)
def test_main(config):
    with mock.patch('dali_mqtt_daemon.create_mqtt_client', return_value=mock.Mock()) as mock_mqtt_client:
        with mock.patch('dali_mqtt_daemon.load_config_file', return_value=config) as mock_config_file:
            mock_mqtt_client.loop_forever = mock.Mock()
            main(config)
            mock_config_file.assert_called()
            assert mock_mqtt_client.call_count == 11