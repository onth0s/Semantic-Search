"""Unit tests for alias and memory import/export CLI commands."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from sempath.cli import cli


@pytest.fixture
def mock_memory_file(tmp_path: Path) -> Path:
    """Provide a mocked memory file path for testing."""
    return tmp_path / "learned_aliases.yaml"


def test_alias_add_and_list(mock_memory_file: Path):
    """alias add adds an alias and alias list lists it."""
    runner = CliRunner()

    with patch("sempath.utils.memory.get_memory_file_path", return_value=mock_memory_file):
        # Add alias
        res_add = runner.invoke(cli, ["alias", "add", "my_shortcut", "C:/User/Docs"])
        assert res_add.exit_code == 0
        assert "Added alias my_shortcut" in res_add.output

        # List aliases
        res_list = runner.invoke(cli, ["alias", "list"])
        assert res_list.exit_code == 0
        assert "my_shortcut" in res_list.output
        assert "C:\\User\\Docs" in res_list.output or "C:/User/Docs" in res_list.output


def test_alias_remove(mock_memory_file: Path):
    """alias remove deletes a learned alias."""
    runner = CliRunner()

    with patch("sempath.utils.memory.get_memory_file_path", return_value=mock_memory_file):
        # Add
        runner.invoke(cli, ["alias", "add", "shortcut", "C:/Path"])

        # Remove
        res_remove = runner.invoke(cli, ["alias", "remove", "shortcut"])
        assert res_remove.exit_code == 0
        assert "Removed alias shortcut" in res_remove.output

        # List to verify it is gone
        res_list = runner.invoke(cli, ["alias", "list"])
        assert "shortcut" not in res_list.output


def test_alias_clear(mock_memory_file: Path):
    """alias clear clears all learned aliases."""
    runner = CliRunner()

    with patch("sempath.utils.memory.get_memory_file_path", return_value=mock_memory_file):
        runner.invoke(cli, ["alias", "add", "sc1", "C:/P1"])
        runner.invoke(cli, ["alias", "add", "sc2", "C:/P2"])

        res_clear = runner.invoke(cli, ["alias", "clear"])
        assert res_clear.exit_code == 0
        assert "All learned aliases cleared" in res_clear.output

        res_list = runner.invoke(cli, ["alias", "list"])
        assert "sc1" not in res_list.output
        assert "sc2" not in res_list.output


def test_alias_undo(mock_memory_file: Path):
    """alias undo pops the latest learned alias."""
    runner = CliRunner()

    with patch("sempath.utils.memory.get_memory_file_path", return_value=mock_memory_file):
        runner.invoke(cli, ["alias", "add", "sc1", "C:/P1"])

        # Undo
        res_undo = runner.invoke(cli, ["alias", "undo"])
        assert res_undo.exit_code == 0
        assert "Reverted last alias" in res_undo.output

        # Undo again when empty
        res_undo_empty = runner.invoke(cli, ["alias", "undo"])
        assert res_undo_empty.exit_code == 0
        assert "No learned aliases to undo" in res_undo_empty.output


def test_export_import_memory(tmp_path: Path, mock_memory_file: Path):
    """export-memory and import-memory successfully backup/restore memory."""
    runner = CliRunner()
    export_file = tmp_path / "export.yaml"

    with patch("sempath.utils.memory.get_memory_file_path", return_value=mock_memory_file):
        # Add alias
        runner.invoke(cli, ["alias", "add", "backup_key", "C:/Backup"])

        # Export
        res_export = runner.invoke(cli, ["export-memory", str(export_file)])
        assert res_export.exit_code == 0
        assert "Exported memory" in res_export.output
        assert export_file.exists()

        # Clear local memory
        runner.invoke(cli, ["alias", "clear"])

        # Import
        res_import = runner.invoke(cli, ["import-memory", str(export_file)])
        assert res_import.exit_code == 0
        assert "Imported memory" in res_import.output

        # Verify alias is back
        res_list = runner.invoke(cli, ["alias", "list"])
        assert "backup_key" in res_list.output
