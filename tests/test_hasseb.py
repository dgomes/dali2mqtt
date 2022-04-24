"""Tests based on hasseb driver."""

from dali2mqtt.dali2mqtt import main
from unittest import mock
import pytest

from dali2mqtt.consts import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_MQTT_SERVER,
    DEFAULT_MQTT_PORT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_COLOR,
    DEFAULT_HA_DISCOVERY_PREFIX,
    MAX_RETRIES,
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
    return {
        "config": "config.yaml",
        "dali_driver": "hasseb",
        "dali_lamps": 2,
        "mqtt_server": "localhost",
        "mqtt_port": 1883,
        "mqtt_base_topic": "dali2mqtt",
        "ha_discovery_prefix": "homeassistant",
        "log_level": "info",
        "log_color": False,
    }

@pytest.fixture
def fake_data_object():
    driver = mock.Mock()
    driver.send = lambda x: 0x00

    return {
        "driver": driver,
        "base_topic": "test",
        "ha_prefix": "hass",
        "log_level": "debug",
        "devices_names_config": None
    }

@pytest.fixture
def fake_mqttc():
    mqttc = mock.Mock()
    def loop_forever():
        import sys
        raise Exception()
    mqttc.loop_forever = loop_forever
    return mqttc


def test_main(args, config, fake_mqttc, caplog):
    """Test main loop."""
    with mock.patch(
        "dali2mqtt.dali2mqtt.create_mqtt_client", return_value=fake_mqttc
    ) as mock_mqtt_client:
        with mock.patch("time.sleep", return_value=None) as sleep:
            main(args)
            assert sleep.call_count == MAX_RETRIES
            assert mock_mqtt_client.call_count == MAX_RETRIES
            assert any("Maximum retries of 10 reached, exiting" in rec.message for rec in caplog.records)
