"""Tests for Lamp level setter — real logic, not mock testing."""

import logging
from unittest import mock

import pytest
from dali.address import Short

from dali2mqtt.lamp import Lamp

# Realistic driver values for Lamp initialization
MIN_PHYSICAL_BRIGHTNESS = 1
MIN_BRIGHTNESS = 2
MAX_BRIGHTNESS = 250
INITIAL_BRIGHTNESS = 100


def _make_driver():
    """Create a mock driver with a sequence of responses.

    Init requires 5 sends: QueryPhysicalMinimum, QueryMinLevel,
    QueryMaxLevel, QueryActualLevel, and the DAPC triggered by the
    level setter inside __init__.
    """
    init_values = [
        MIN_PHYSICAL_BRIGHTNESS,  # QueryPhysicalMinimum
        MIN_BRIGHTNESS,           # QueryMinLevel
        MAX_BRIGHTNESS,           # QueryMaxLevel
        INITIAL_BRIGHTNESS,       # QueryActualLevel
        None,                     # DAPC call from setter in __init__
    ]

    values = iter(init_values)

    def send(cmd):
        result = mock.Mock()
        result.value = next(values)
        return result

    driver = mock.Mock()
    driver.send = mock.Mock(side_effect=send)
    return driver


def _make_lamp():
    """Create a Lamp with a mock driver, using real Lamp logic."""
    driver = _make_driver()
    addr = Short(1)
    lamp = Lamp(
        log_level="debug",
        driver=driver,
        friendly_name="test lamp",
        short_address=addr,
    )
    return lamp, driver


class TestLevelSetter:
    """Test the real Lamp.level setter logic."""

    def test_set_numeric_level_within_range(self):
        """Setting a valid numeric level should update __level and call DAPC."""
        lamp, driver = _make_lamp()
        # Reset mock to track only post-init calls
        driver.send.reset_mock()
        driver.send.side_effect = None
        driver.send.return_value = mock.Mock()

        lamp.level = 128
        assert lamp.level == 128
        driver.send.assert_called_once()

    def test_set_non_numeric_string_mask_ignored(self, caplog):
        """Non-numeric 'MASK' must be rejected with a warning, level unchanged."""
        lamp, driver = _make_lamp()
        driver.send.reset_mock()

        original_level = lamp.level
        assert original_level == INITIAL_BRIGHTNESS

        with caplog.at_level(logging.WARNING, logger="dali2mqtt.lamp"):
            lamp.level = "MASK"

        # Level must NOT change
        assert lamp.level == original_level
        # DAPC must NOT have been sent
        driver.send.assert_not_called()
        # Warning must be logged
        assert any("Ignoring non-numeric level value" in r.message for r in caplog.records)

    def test_set_non_numeric_none_ignored(self, caplog):
        """Non-numeric None must be rejected with a warning, level unchanged."""
        lamp, driver = _make_lamp()
        driver.send.reset_mock()

        with caplog.at_level(logging.WARNING, logger="dali2mqtt.lamp"):
            lamp.level = None

        assert lamp.level == INITIAL_BRIGHTNESS
        driver.send.assert_not_called()

    def test_set_numeric_out_of_range_raises_value_error(self):
        """A numeric value outside [min_level, max_level] (and != 0) raises ValueError."""
        lamp, driver = _make_lamp()
        driver.send.reset_mock()

        with pytest.raises(ValueError):
            lamp.level = 300  # above max_level (250)
        assert lamp.level == INITIAL_BRIGHTNESS

    def test_set_numeric_below_min_raises_value_error(self):
        """A numeric value below min_level (and != 0) raises ValueError."""
        lamp, driver = _make_lamp()
        driver.send.reset_mock()

        with pytest.raises(ValueError):
            lamp.level = 1  # below min_level (2), and != 0
        assert lamp.level == INITIAL_BRIGHTNESS

    def test_set_level_zero_is_allowed(self):
        """Level 0 is a special case (off) and should be accepted."""
        lamp, driver = _make_lamp()
        driver.send.reset_mock()
        driver.send.side_effect = None
        driver.send.return_value = mock.Mock()

        lamp.level = 0
        assert lamp.level == 0
        driver.send.assert_called_once()

    def test_set_level_at_min_boundary(self):
        """Setting level exactly at min_level should work."""
        lamp, driver = _make_lamp()
        driver.send.reset_mock()
        driver.send.side_effect = None
        driver.send.return_value = mock.Mock()

        lamp.level = MIN_BRIGHTNESS
        assert lamp.level == MIN_BRIGHTNESS

    def test_set_level_at_max_boundary(self):
        """Setting level exactly at max_level should work."""
        lamp, driver = _make_lamp()
        driver.send.reset_mock()
        driver.send.side_effect = None
        driver.send.return_value = mock.Mock()

        lamp.level = MAX_BRIGHTNESS
        assert lamp.level == MAX_BRIGHTNESS
