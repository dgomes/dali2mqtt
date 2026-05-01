"""Tests for DevicesNamesConfig."""

import os
import tempfile
import pytest
import yaml
from dali2mqtt.devicesnamesconfig import DevicesNamesConfig, DevicesNamesConfigLoadError


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def config_file(temp_dir):
    return os.path.join(temp_dir, "devices.yaml")


@pytest.fixture
def config_with_devices(temp_dir):
    """Create a config file with some devices."""
    path = os.path.join(temp_dir, "devices.yaml")
    data = {
        0: {"friendly_name": "Living Room"},
        1: {"friendly_name": "Kitchen"},
    }
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


def test_load_existing_config(config_with_devices):
    """Test loading an existing config file."""
    config = DevicesNamesConfig("info", config_with_devices)
    assert config.get_friendly_name(0) == "Living Room"
    assert config.get_friendly_name(1) == "Kitchen"


def test_get_friendly_name_unknown_address(config_file):
    """Test getting friendly name for unknown address returns address as string."""
    config = DevicesNamesConfig("info", config_file)
    assert config.get_friendly_name(99) == "99"


def test_is_devices_file_empty_true(config_file):
    """Test that empty file returns True."""
    config = DevicesNamesConfig("info", config_file)
    assert config.is_devices_file_empty() is True


def test_is_devices_file_empty_false(config_with_devices):
    """Test that non-empty file returns False."""
    config = DevicesNamesConfig("info", config_with_devices)
    assert config.is_devices_file_empty() is False


def test_save_devices_names_file(config_file):
    """Test saving device names to file."""
    config = DevicesNamesConfig("info", config_file)

    # Create mock lamp objects
    lamp1 = type(
        "Lamp",
        (),
        {"short_address": type("Addr", (), {"address": 0})()},
    )()
    lamp2 = type(
        "Lamp",
        (),
        {"short_address": type("Addr", (), {"address": 1})()},
    )()

    all_lamps = {"lamp1": lamp1, "lamp2": lamp2}
    config.save_devices_names_file(all_lamps)

    # Reload and verify
    config2 = DevicesNamesConfig("info", config_file)
    assert config2.get_friendly_name(0) == "0"
    assert config2.get_friendly_name(1) == "1"


def test_load_invalid_yaml_raises(temp_dir):
    """Test that invalid YAML raises DevicesNamesConfigLoadError."""
    path = os.path.join(temp_dir, "bad.yaml")
    with open(path, "w") as f:
        f.write("{{invalid yaml content")

    with pytest.raises(DevicesNamesConfigLoadError):
        DevicesNamesConfig("info", path)


def test_load_devices_names_file(config_with_devices):
    """Test explicit load_devices_names_file call."""
    config = DevicesNamesConfig("info", config_with_devices)
    # Should not raise
    config.load_devices_names_file()
    assert config.get_friendly_name(0) == "Living Room"


def test_get_friendly_name_returns_string(config_with_devices):
    """Test that get_friendly_name always returns a string."""
    config = DevicesNamesConfig("info", config_with_devices)
    result = config.get_friendly_name(0)
    assert isinstance(result, str)

    # Unknown address should also return string
    result = config.get_friendly_name(999)
    assert isinstance(result, str)
    assert result == "999"


def test_save_and_reload_roundtrip(config_file):
    """Test that save → load roundtrip preserves data."""
    config = DevicesNamesConfig("info", config_file)

    lamp1 = type(
        "Lamp",
        (),
        {"short_address": type("Addr", (), {"address": 42})()},
    )()
    config.save_devices_names_file({"lamp1": lamp1})

    # Reload
    config2 = DevicesNamesConfig("info", config_file)
    assert config2.get_friendly_name(42) == "42"
    assert not config2.is_devices_file_empty()
