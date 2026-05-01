"""Tests for lamp level handling edge cases."""

from dali2mqtt.lamp import Lamp
from unittest import mock
from dali.address import Short
import pytest


MIN_PHYSICAL_BRIGHTNESS = 1
MIN_BRIGHTNESS = 2
MAX_BRIGHTNESS = 250
ACTUAL_BRIGHTNESS = 100


def generate_driver_values(results):
    for res in results:
        result = mock.Mock()
        result.value = res
        yield result


@pytest.fixture
def fake_driver():
    """Driver with enough values for Lamp.__init__.

    Init consumes 5 driver calls:
    1. QueryPhysicalMinimum -> MIN_PHYSICAL_BRIGHTNESS
    2. QueryMinLevel -> MIN_BRIGHTNESS
    3. QueryMaxLevel -> MAX_BRIGHTNESS
    4. QueryActualLevel -> ACTUAL_BRIGHTNESS (.value)
    5. DAPC (from level setter in __init__) -> ACTUAL_BRIGHTNESS
    """
    drive = mock.Mock()
    drive.dummy = generate_driver_values(
        [MIN_PHYSICAL_BRIGHTNESS, MIN_BRIGHTNESS, MAX_BRIGHTNESS, ACTUAL_BRIGHTNESS, ACTUAL_BRIGHTNESS]
    )
    drive.send = lambda x: next(drive.dummy)
    return drive


@pytest.fixture
def lamp(fake_driver):
    """A fully initialized Lamp with a mock driver."""
    return Lamp(
        log_level="debug",
        driver=fake_driver,
        friendly_name="test lamp",
        short_address=Short(1),
    )


def test_level_setter_valid_value(lamp):
    """Test setting a valid brightness level."""
    lamp.driver = mock.Mock()
    lamp.level = 50
    assert lamp.level == 50


def test_level_setter_zero(lamp):
    """Test that 0 is always accepted (turn off)."""
    lamp.driver = mock.Mock()
    lamp.level = 0
    assert lamp.level == 0


def test_level_setter_max_boundary(lamp):
    """Test setting level to max boundary."""
    lamp.driver = mock.Mock()
    lamp.level = MAX_BRIGHTNESS
    assert lamp.level == MAX_BRIGHTNESS


def test_level_setter_min_boundary(lamp):
    """Test setting level to min boundary."""
    lamp.driver = mock.Mock()
    lamp.level = MIN_BRIGHTNESS
    assert lamp.level == MIN_BRIGHTNESS


def test_level_setter_above_max_raises(lamp):
    """Test that level above max raises ValueError."""
    lamp.driver = mock.Mock()
    with pytest.raises(ValueError):
        lamp.level = MAX_BRIGHTNESS + 1


def test_level_setter_below_min_nonzero_raises(lamp):
    """Test that level below min (non-zero) raises ValueError."""
    lamp.driver = mock.Mock()
    with pytest.raises(ValueError):
        lamp.level = MIN_BRIGHTNESS - 1


def test_level_setter_string_value_raises(lamp):
    """Test that string value (e.g., MASK) raises TypeError.

    DALI devices may return 'MASK' when a value is not available.
    This currently causes TypeError on int/str comparison.
    Issue: https://github.com/dgomes/dali2mqtt/issues/64
    """
    lamp.driver = mock.Mock()
    with pytest.raises(TypeError):
        lamp.level = "MASK"


def test_level_setter_nan_raises(lamp):
    """Test that NaN value is handled.

    NaN comparison with int always returns False, so the bounds check
    `not min_level <= value <= max_level` would be True (NaN comparisons
    are always False), and with value != 0 also True, so it raises ValueError.
    """
    lamp.driver = mock.Mock()
    with pytest.raises(ValueError):
        lamp.level = float("nan")


def test_off_method(lamp):
    """Test turning off the lamp."""
    lamp.driver = mock.Mock()
    lamp.off()
    lamp.driver.send.assert_called_once()


def test_str_representation(lamp):
    """Test string representation of lamp."""
    result = str(lamp)
    assert "test-lamp" in result
    assert "address: 1" in result
    assert f"actual brightness level: {ACTUAL_BRIGHTNESS}" in result
    assert f"minimum: {MIN_BRIGHTNESS}" in result
    assert f"max: {MAX_BRIGHTNESS}" in result


def test_actual_level_updates(lamp):
    """Test that actual_level() queries the driver and updates __level."""
    mock_response = mock.Mock()
    mock_response.value = 75
    lamp.driver = mock.Mock()
    lamp.driver.send.return_value = mock_response
    lamp.actual_level()
    # actual_level stores the raw response (not .value)
    assert lamp.level == mock_response


def test_gen_ha_config_returns_valid_json(lamp):
    """Test that gen_ha_config returns valid JSON."""
    import json

    config_json = lamp.gen_ha_config("test_topic")
    config = json.loads(config_json)
    assert config["name"] == "test lamp"
    assert "stat_t" in config
    assert "cmd_t" in config
    assert "bri_scl" in config
    assert config["bri_scl"] == MAX_BRIGHTNESS


def test_level_setter_sends_dapc(lamp):
    """Test that setting level sends DAPC command to driver."""
    lamp.driver = mock.Mock()
    lamp.level = 50
    lamp.driver.send.assert_called_once()


def test_level_setter_int_value_accepted(lamp):
    """Test that int values are properly handled."""
    lamp.driver = mock.Mock()
    for val in [MIN_BRIGHTNESS, 100, MAX_BRIGHTNESS, 0]:
        lamp.level = val
        assert lamp.level == val
