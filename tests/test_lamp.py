"""Tests for lamp."""

from dali2mqtt.lamp import Lamp
from dali2mqtt.consts import __version__
from unittest import mock
from dali.address import Group, Short
from dali.frame import BackwardFrameError
import pytest
import json
from slugify import slugify

MIN__PHYSICAL_BRIGHTNESS = 1
MIN_BRIGHTNESS = 2
MAX_BRIGHTNESS = 250
ACTUAL_BRIGHTNESS = 100

def generate_driver_values(results):
    for res in results:
        result = mock.Mock()
        result.value = res
        print(result.value)
        yield result

@pytest.fixture
def fake_driver():
    drive = mock.Mock()
    drive.dummy = generate_driver_values([MIN__PHYSICAL_BRIGHTNESS, MIN_BRIGHTNESS, MAX_BRIGHTNESS, ACTUAL_BRIGHTNESS, ACTUAL_BRIGHTNESS])
    drive.send = lambda x: next(drive.dummy)
    return drive


@pytest.fixture
def fake_address():
    address = mock.Mock()
    address.address = 1
    address.__repr__ = lambda: "1"

def test_ha_config(fake_driver, fake_address):

    friendly_name = "my lamp"
    addr_number = 1
    addr = Short(1)

    lamp1 = Lamp(
        log_level="debug",
        driver=fake_driver,
        friendly_name=friendly_name,
        short_address=addr,
    )

    assert lamp1.device_name == slugify(friendly_name)
    assert lamp1.short_address.address == addr_number

    assert str(lamp1) == f'my-lamp - address: {addr_number}, actual brightness level: {ACTUAL_BRIGHTNESS} (minimum: {MIN_BRIGHTNESS}, max: {MAX_BRIGHTNESS}, physical minimum: {MIN__PHYSICAL_BRIGHTNESS})'

    assert json.loads(lamp1.gen_ha_config("test")) == {
        "name": friendly_name,
        "def_ent_id": "dali_light_my-lamp",
        "uniq_id": f"Mock_{addr}",
        "stat_t": "test/my-lamp/light/status",
        "cmd_t": "test/my-lamp/light/switch",
        "pl_off": "OFF",
        "bri_stat_t": "test/my-lamp/light/brightness/status",
        "bri_cmd_t": "test/my-lamp/light/brightness/set",
        "bri_scl": MAX_BRIGHTNESS,
        "on_cmd_type": "brightness",
        "avty_t": "test/status",
        "pl_avail": "online",
        "pl_not_avail": "offline",
        "device": {
            "ids": "dali2mqtt",
            "name": "DALI Lights",
            "sw": f"dali2mqtt {__version__}",
            "mdl": "Mock",
            "mf": "dali2mqtt",
        },
    }


@pytest.fixture
def colliding_bus():
    """A bus where every answer is a framing error.

    That's what a group query returns when its members answer differently,
    e.g. one lamp is on and another is off.
    """
    driver = mock.Mock()
    driver.send = mock.Mock(
        side_effect=lambda cmd: cmd.response(BackwardFrameError(255))
        if cmd.response
        else None
    )
    return driver


def test_group_lamp_initializes_without_querying_bus(colliding_bus):
    lamp = Lamp("debug", colliding_bus, "group_1", Group(1))

    assert lamp.is_group
    assert (lamp.min_level, lamp.max_level, lamp.level) == (1, 254, 0)
    assert lamp.min_physical_level is None
    colliding_bus.send.assert_not_called()


def test_group_lamp_actual_level_does_not_query_bus(colliding_bus):
    lamp = Lamp("debug", colliding_bus, "group_1", Group(1))
    lamp.actual_level()

    assert lamp.level == 0
    colliding_bus.send.assert_not_called()


def test_group_lamp_str():
    lamp = Lamp("debug", mock.Mock(), "group 1", Group(1))

    assert str(lamp) == (
        f"group-1 - address: {Group(1)}, actual brightness level: 0 "
        "(minimum: 1, max: 254, physical minimum: None)"
    )


def test_group_lamp_still_controls_the_group():
    driver = mock.Mock()
    lamp = Lamp("debug", driver, "group_1", Group(1))

    lamp.level = 200
    lamp.off()

    sent = [c.args[0] for c in driver.send.call_args_list]
    assert [type(cmd).__name__ for cmd in sent] == ["DAPC", "Off"]
    assert all(cmd.destination == Group(1) for cmd in sent)

