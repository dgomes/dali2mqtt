"""Tests for MQTT command handling."""

from unittest import mock

from dali.address import Group, Short

from dali2mqtt.dali2mqtt import on_message_brightness_cmd
from dali2mqtt.lamp import Lamp


def make_data_object():
    driver = mock.Mock()
    # Lamp queries: physical minimum, min level, max level, actual level
    driver.send = mock.Mock(
        side_effect=[mock.Mock(value=v) for v in (85, 85, 254, 0)] + [None] * 10
    )
    # initialize_lamps stores lamps by friendly name and groups as group_<n>
    all_lamps = {
        "kitchen": Lamp("debug", driver, "kitchen", Short(0)),
        "group_1": Lamp("debug", driver, "group_1", Group(1)),
    }
    driver.send.reset_mock()
    return {"driver": driver, "base_topic": "dali2mqtt", "all_lamps": all_lamps}


def test_brightness_command_reaches_group():
    data = make_data_object()
    msg = mock.Mock(topic="dali2mqtt/group_1/light/brightness/set", payload=b"200")

    on_message_brightness_cmd(mock.Mock(), data, msg)

    (cmd,), _ = data["driver"].send.call_args
    assert type(cmd).__name__ == "DAPC"
    assert cmd.destination == Group(1)
    assert data["all_lamps"]["group_1"].level == 200


def test_brightness_command_reaches_lamp():
    data = make_data_object()
    msg = mock.Mock(topic="dali2mqtt/kitchen/light/brightness/set", payload=b"150")

    on_message_brightness_cmd(mock.Mock(), data, msg)

    (cmd,), _ = data["driver"].send.call_args
    assert cmd.destination == Short(0)
    assert data["all_lamps"]["kitchen"].level == 150
