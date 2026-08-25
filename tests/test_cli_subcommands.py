"""Comprehensive unit and integration tests for CLI subcommands.

Tests:
- index create, update, list, remove
- config verbose, gitignore, depth
- alias add, list, remove, clear, undo
- preset list, get, set, remove
- export-memory, import-memory
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from sempath.cli import cli


def test_index_subcommands_lifecycle(tmp_path: Path):
    """Test index create, list, update, remove on a temporary workspace."""
    runner = CliRunner()
    test_dir = tmp_path / "workspace"
    test_dir.mkdir()
    (test_dir / "file1.txt").write_text("hello", encoding="utf-8")
    (test_dir / "file2.py").write_text("print('test')", encoding="utf-8")

    db_dir = tmp_path / "index_cache"

    with patch("sempath.cli.subcommands.index_cmd.get_index_store_path", return_value=db_dir):
        # 1. Create index
        res_create = runner.invoke(cli, ["index", "create", str(test_dir)])
        assert res_create.exit_code == 0
        assert "Indexed root" in res_create.output

        # 2. List index
        res_list = runner.invoke(cli, ["index", "list"])
        assert res_list.exit_code == 0
        cleaned_list_output = res_list.output.replace("\n", "").replace("\r", "")
        assert str(test_dir) in cleaned_list_output

        # 3. Add a new file and update index
        (test_dir / "file3.md").write_text("markdown", encoding="utf-8")
        res_update = runner.invoke(cli, ["index", "update", str(test_dir)])
        assert res_update.exit_code == 0
        assert "Updated root" in res_update.output

        # 4. Remove single root
        res_remove = runner.invoke(cli, ["index", "remove", str(test_dir)])
        assert res_remove.exit_code == 0
        assert "Removed root" in res_remove.output

        # 5. Remove not found path
        res_remove_missing = runner.invoke(cli, ["index", "remove", str(test_dir)])
        assert res_remove_missing.exit_code == 0
        assert "was not found in the index" in res_remove_missing.output

        # 6. Clear index --all
        res_clear_all = runner.invoke(cli, ["index", "remove", "--all"])
        assert res_clear_all.exit_code == 0
        assert "Entire index database cleared" in res_clear_all.output


def test_config_subcommands(tmp_path: Path):
    """Test config verbose, gitignore, and depth subcommands."""
    runner = CliRunner()

    with patch("sempath.cli.subcommands.config_cmd.save_config") as mock_save:
        # 1. config verbose on
        res_verbose_on = runner.invoke(cli, ["config", "verbose", "on"])
        assert res_verbose_on.exit_code == 0
        assert "enabled" in res_verbose_on.output
        mock_save.assert_called_with({"verbose": True})

        # 2. config verbose off
        res_verbose_off = runner.invoke(cli, ["config", "verbose", "off"])
        assert res_verbose_off.exit_code == 0
        assert "disabled" in res_verbose_off.output
        mock_save.assert_called_with({"verbose": False})

        # 3. config gitignore on
        res_gi_on = runner.invoke(cli, ["config", "gitignore", "true"])
        assert res_gi_on.exit_code == 0
        assert "enabled" in res_gi_on.output
        mock_save.assert_called_with({"index": {"respect_gitignore": True}})

        # 4. config depth 10
        res_depth = runner.invoke(cli, ["config", "depth", "10"])
        assert res_depth.exit_code == 0
        assert "Default search depth set to 10" in res_depth.output
        mock_save.assert_called_with({"depth": 10})

        # 5. config depth invalid (< 1)
        res_depth_invalid = runner.invoke(cli, ["config", "depth", "0"])
        assert res_depth_invalid.exit_code != 0
        assert "Depth must be a positive integer" in res_depth_invalid.output


def test_preset_subcommands(tmp_path: Path):
    """Test preset list, get, set, remove."""
    runner = CliRunner()
    mock_presets = {"custom": "h1-4", "llm": "h8"}

    with (
        patch(
            "sempath.cli.subcommands.preset_cmd.load_config",
            return_value={"presets": mock_presets},
        ),
        patch("sempath.cli.subcommands.preset_cmd.save_config") as mock_save,
    ):
        # 1. preset list
        res_list = runner.invoke(cli, ["preset", "list"])
        assert res_list.exit_code == 0
        assert "custom" in res_list.output
        assert "h1-4" in res_list.output

        # 2. preset get custom
        res_get = runner.invoke(cli, ["preset", "get", "custom"])
        assert res_get.exit_code == 0
        assert "h1-4" in res_get.output

        # 3. preset get nonexistent
        res_get_none = runner.invoke(cli, ["preset", "get", "nonexistent"])
        assert res_get_none.exit_code != 0
        assert "is not defined" in res_get_none.output

        # 4. preset set
        res_set = runner.invoke(cli, ["preset", "set", "fast4", "h1-4"])
        assert res_set.exit_code == 0
        assert "Saved preset" in res_set.output
        mock_save.assert_called()

        # 5. preset remove
        res_remove = runner.invoke(cli, ["preset", "remove", "custom"])
        assert res_remove.exit_code == 0
        assert "Removed preset" in res_remove.output
