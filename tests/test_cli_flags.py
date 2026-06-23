"""Unit tests for explicit flags in find command (--latest, --largest, --ext)."""

import os
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.cli import cli


@pytest.fixture
def mock_temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory structure for CLI flag testing."""
    f1 = tmp_path / "file1.txt"
    f1.write_text("small", encoding="utf-8")  # 5 bytes

    f2 = tmp_path / "file2.txt"
    f2.write_text("much larger text here", encoding="utf-8")  # 21 bytes

    f3 = tmp_path / "image.png"
    f3.write_text("png", encoding="utf-8")

    # set times: f1 is newer than f2
    now = time.time()
    os.utime(f1, (now, now))
    os.utime(f2, (now - 100, now - 100))

    return tmp_path


def test_find_ext_flag(mock_temp_dir: Path):
    """find --ext png matches only png files."""
    runner = CliRunner()
    # Query is "." which bypasses to first match under the filtered candidates
    result = runner.invoke(cli, ["find", "--ext", "png", ".", str(mock_temp_dir)])
    assert result.exit_code == 0
    assert "image.png" in result.output


def test_find_latest_flag(mock_temp_dir: Path):
    """find --latest matches the newest file."""
    runner = CliRunner()
    result = runner.invoke(cli, ["find", "--latest", "--ext", "txt", ".", str(mock_temp_dir)])
    assert result.exit_code == 0
    assert "file1.txt" in result.output  # file1 is newer


def test_find_largest_flag(mock_temp_dir: Path):
    """find --largest matches the largest file."""
    runner = CliRunner()
    result = runner.invoke(cli, ["find", "--largest", "--ext", "txt", ".", str(mock_temp_dir)])
    assert result.exit_code == 0
    assert "file2.txt" in result.output  # file2 is larger (21 bytes vs 5)


def test_help_full_flag():
    """--help-full flag prints help for all commands recursively and exits 0."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help-full"])
    assert result.exit_code == 0
    # Check that it printed output for all major commands/subcommands
    assert "COMMAND: sempath" in result.output or "COMMAND: cli" in result.output
    assert "find" in result.output
    assert "index create" in result.output
    assert "alias add" in result.output
    assert "export-memory" in result.output
    assert "import-memory" in result.output
