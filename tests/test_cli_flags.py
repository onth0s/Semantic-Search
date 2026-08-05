"""Unit tests for explicit flags in find command (--latest, --largest, --ext)."""

import os
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from sempath.cli import cli


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


def test_find_oldest_flag(mock_temp_dir: Path):
    """find --oldest matches the oldest file."""
    runner = CliRunner()
    result = runner.invoke(cli, ["find", "--oldest", "--ext", "txt", ".", str(mock_temp_dir)])
    assert result.exit_code == 0
    assert "file2.txt" in result.output  # file2 is older (100 seconds older)


def test_find_largest_flag(mock_temp_dir: Path):
    """find --largest matches the largest file."""
    runner = CliRunner()
    result = runner.invoke(cli, ["find", "--largest", "--ext", "txt", ".", str(mock_temp_dir)])
    assert result.exit_code == 0
    assert "file2.txt" in result.output  # file2 is larger (21 bytes vs 5)


def test_find_smallest_flag(mock_temp_dir: Path):
    """find --smallest matches the smallest file."""
    runner = CliRunner()
    result = runner.invoke(cli, ["find", "--smallest", "--ext", "txt", ".", str(mock_temp_dir)])
    assert result.exit_code == 0
    assert "file1.txt" in result.output  # file1 is smaller (5 bytes vs 21)


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


def test_find_verbose_output_control(mock_temp_dir: Path):
    """Test that confidence and handler metadata is only present when verbose is on."""
    runner = CliRunner()

    # Ensure config verbose is set to off initially
    runner.invoke(cli, ["config", "verbose", "off"])

    # 1. Without --verbose: metadata is hidden
    res_non_verbose = runner.invoke(cli, ["find", "--ext", "png", ".", str(mock_temp_dir)])
    assert res_non_verbose.exit_code == 0
    assert "image.png" in res_non_verbose.output
    assert "confidence" not in res_non_verbose.output
    assert "explicit_flags" not in res_non_verbose.output

    # 2. With --verbose: metadata is shown
    res_verbose = runner.invoke(cli, ["find", "--ext", "png", "--verbose", ".", str(mock_temp_dir)])
    assert res_verbose.exit_code == 0
    assert "image.png" in res_verbose.output
    assert "confidence" in res_verbose.output
    assert "explicit_flags" in res_verbose.output


def test_negative_integer_clamp(mock_temp_dir: Path):
    """Test that -[integer] shortcut successfully clamps results (even with exhaustive)."""
    runner = CliRunner()
    # Invoke with -1 to clamp results to 1, even if multiple match
    result = runner.invoke(cli, ["find", "--ext", "txt", ".", "-1", str(mock_temp_dir)])
    assert result.exit_code == 0
    # There should only be one match shown (e.g. file1.txt or file2.txt, not both)
    lines = [line for line in result.output.splitlines() if line.strip()]
    # Check if there is only 1 file listed. When top_n=1, only main match is output (no near-miss).
    # The output contains the single file path.
    txt_matches = [line for line in lines if "file" in line]
    assert len(txt_matches) == 1


def test_find_gitignore_flags(tmp_path: Path):
    """Test that find --gitignore flips the respect_gitignore config value."""
    # Create a gitignored file
    (tmp_path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")

    ignored_file = tmp_path / "ignored.txt"
    ignored_file.write_text("secret", encoding="utf-8")

    runner = CliRunner()

    # --- Case A: Config defaults to True (respect) ---
    runner.invoke(cli, ["config", "gitignore", "on"])
    # 1. Without flag: explicit root str(tmp_path) takes precedence
    # (default_respect is False, so ignored.txt IS found)
    res1 = runner.invoke(cli, ["find", "ignored.txt", str(tmp_path)])
    assert res1.exit_code == 0
    assert "ignored.txt" in res1.output
    # 2. With --gitignore flag: flips behavior to True (respect gitignore)
    # so ignored.txt is NOT found
    res2 = runner.invoke(cli, ["find", "--gitignore", "ignored.txt", str(tmp_path)])
    assert "ignored.txt" not in res2.output

    # --- Case B: Config set to False (ignore) ---
    runner.invoke(cli, ["config", "gitignore", "off"])
    # 3. Without flag: explicit root str(tmp_path) takes precedence
    # (default_respect is False, so ignored.txt IS found)
    res3 = runner.invoke(cli, ["find", "ignored.txt", str(tmp_path)])
    assert res3.exit_code == 0
    assert "ignored.txt" in res3.output
    # 4. With --gitignore flag: flips behavior to True (respect gitignore)
    # so ignored.txt is NOT found
    res4 = runner.invoke(cli, ["find", "--gitignore", "ignored.txt", str(tmp_path)])
    assert "ignored.txt" not in res4.output


def test_config_gitignore():
    """Test that sempath config gitignore updates config properly."""
    runner = CliRunner()

    # Disable respecting gitignore globally via config
    res_off = runner.invoke(cli, ["config", "gitignore", "off"])
    assert res_off.exit_code == 0
    assert "Respecting .gitignore rules has been disabled" in res_off.output

    # Enable respecting gitignore globally via config
    res_on = runner.invoke(cli, ["config", "gitignore", "on"])
    assert res_on.exit_code == 0
    assert "Respecting .gitignore rules has been enabled" in res_on.output


def test_find_read_content_flag(tmp_path: Path):
    """Test that find --read-content searches within readable text files and ignores binaries."""
    # 1. Create a readable text file
    txt_file = tmp_path / "hello.txt"
    txt_file.write_text("Hello VIEW3D PT_sculpt_symmetry_for_topbar world!", encoding="utf-8")

    # 2. Create a binary file containing the target string but with a null byte
    bin_file = tmp_path / "data.bin"
    bin_file.write_bytes(b"\x00VIEW3D PT_sculpt_symmetry_for_topbar\x00")

    runner = CliRunner()

    # Default behaviour: disabled, so no content search is performed
    res_default = runner.invoke(cli, ["find", "sculpt_symmetry", str(tmp_path)])
    assert "hello.txt" not in res_default.output

    # Enabled behaviour: search within content
    res_content = runner.invoke(cli, ["find", "--read-content", "sculpt_symmetry", str(tmp_path)])
    assert res_content.exit_code == 0
    assert "hello.txt" in res_content.output
    assert "data.bin" not in res_content.output


def test_find_handlers_double_dashes(tmp_path: Path):
    """Test that find --handlers and shorthand options accept double-dashed values."""
    txt_file = tmp_path / "hello.txt"
    txt_file.write_text("Hello", encoding="utf-8")

    runner = CliRunner()

    # 1. Single handler specification via --handlers
    res1 = runner.invoke(cli, ["find", "--handlers", "--h1", "hello", str(tmp_path)])
    assert res1.exit_code == 0
    assert "hello.txt" in res1.output

    # 2. Range handler specification via --handlers
    res2 = runner.invoke(cli, ["find", "--handlers", "--h1-3", "hello", str(tmp_path)])
    assert res2.exit_code == 0
    assert "hello.txt" in res2.output

    # 3. Shorthand options directly (e.g. --h1, --h1-3)
    res3 = runner.invoke(cli, ["find", "--h1", "hello", str(tmp_path)])
    assert res3.exit_code == 0
    assert "hello.txt" in res3.output

    res4 = runner.invoke(cli, ["find", "--h1-3", "hello", str(tmp_path)])
    assert res4.exit_code == 0
    assert "hello.txt" in res4.output


def test_preset_commands_and_shorthand(tmp_path: Path):
    """Test preset CLI subcommands and -p0 shorthand resolution."""
    txt_file = tmp_path / "hello.txt"
    txt_file.write_text("Hello", encoding="utf-8")

    runner = CliRunner()

    # 1. Test preset list command
    res_list = runner.invoke(cli, ["preset", "list"])
    assert res_list.exit_code == 0
    assert "sempath Handler Presets" in res_list.output
    assert "h1-6" in res_list.output

    # 2. Test preset get command
    res_get = runner.invoke(cli, ["preset", "get", "0"])
    assert res_get.exit_code == 0
    assert "Preset '0': h1-6" in res_get.output

    # 3. Test preset set command
    res_set = runner.invoke(cli, ["preset", "set", "custom", "h1,h2"])
    assert res_set.exit_code == 0
    assert "Saved preset 'custom'" in res_set.output

    # 4. Test find with -p0 shorthand
    res_p0 = runner.invoke(cli, ["find", "-p0", "hello", str(tmp_path)])
    assert res_p0.exit_code == 0
    assert "hello.txt" in res_p0.output

    # 5. Test find with -p custom shorthand
    res_pc = runner.invoke(cli, ["find", "-p", "custom", "hello", str(tmp_path)])
    assert res_pc.exit_code == 0
    assert "hello.txt" in res_pc.output

    # 6. Test preset remove command
    res_rem = runner.invoke(cli, ["preset", "remove", "custom"])
    assert res_rem.exit_code == 0
    assert "Removed preset 'custom'" in res_rem.output
