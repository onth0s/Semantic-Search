"""Tests for src.config — load_config, DEFAULT_CONFIG, and expand_env_vars."""

from pathlib import Path
from unittest.mock import patch

from src.config import DEFAULT_CONFIG, expand_env_vars, load_config


class TestLoadConfigDefaults:
    """Tests for load_config when no path is provided."""

    def test_load_config_none_returns_valid_dict(self):
        """load_config(None) returns a valid config dict with all expected keys."""
        config = load_config(None)
        assert isinstance(config, dict)
        assert "handlers" in config
        assert "index" in config
        assert "aliases" in config

    def test_load_config_none_has_handlers_section(self):
        """Default config has a handlers section with expected sub-keys."""
        config = load_config(None)
        handlers = config["handlers"]
        assert "enabled" in handlers
        assert "h4_threshold" in handlers
        assert "h7_model" in handlers
        assert "h8_provider" in handlers
        assert "h8_model" in handlers
        assert "h8_url" in handlers
        assert "h9_timeout" in handlers

    def test_default_config_has_all_9_handlers_enabled(self):
        """Default config has all 9 handlers enabled (h1 through h9)."""
        config = load_config(None)
        enabled = config["handlers"]["enabled"]
        expected = ["h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8", "h9"]
        assert enabled == expected

    def test_default_config_matches_module_constant(self):
        """load_config(None) returns the same structure as DEFAULT_CONFIG."""
        config = load_config(None)
        assert config["handlers"]["enabled"] == DEFAULT_CONFIG["handlers"]["enabled"]
        assert config["handlers"]["h4_threshold"] == DEFAULT_CONFIG["handlers"]["h4_threshold"]


class TestLoadConfigFromFile:
    """Tests for load_config with a valid YAML file path."""

    def test_load_config_from_file(self, temp_config_file: Path):
        """load_config(path) with a valid YAML file loads correctly."""
        config = load_config(temp_config_file)
        assert isinstance(config, dict)
        assert "handlers" in config
        assert config["handlers"]["h4_threshold"] == 75

    def test_config_merges_user_values_over_defaults(self, tmp_path: Path):
        """Config merges user values over defaults (e.g., changing h4_threshold)."""
        import yaml

        user_config = {"handlers": {"h4_threshold": 90}}
        config_path = tmp_path / "custom_config.yaml"
        config_path.write_text(yaml.dump(user_config, default_flow_style=False), encoding="utf-8")

        config = load_config(config_path)
        # The user-specified threshold should override the default
        assert config["handlers"]["h4_threshold"] == 90
        # Other default values should still be present
        assert "enabled" in config["handlers"]


class TestExpandEnvVars:
    """Tests for expand_env_vars utility."""

    def test_expand_appdata_on_windows(self):
        """expand_env_vars expands %APPDATA% on Windows."""
        mock_appdata = "C:\\Users\\TestUser\\AppData\\Roaming"
        with patch.dict("os.environ", {"APPDATA": mock_appdata}):
            result = expand_env_vars("%APPDATA%\\sempath\\cache")
            assert isinstance(result, Path)
            assert "TestUser" in str(result)
            assert "sempath" in str(result)

    def test_expand_env_vars_no_vars(self):
        """expand_env_vars returns Path unchanged when no env vars are present."""
        result = expand_env_vars("C:\\some\\literal\\path")
        assert isinstance(result, Path)
        assert str(result) == "C:\\some\\literal\\path"
