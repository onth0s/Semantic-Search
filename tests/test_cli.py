"""Tests for sempath.cli — Click CLI interface using CliRunner."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from sempath.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click CliRunner instance."""
    return CliRunner()


class TestCliHelp:
    """Tests for the top-level CLI help output."""

    def test_cli_help_exits_0(self, runner: CliRunner):
        """cli --help exits with code 0."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_cli_help_contains_sempath(self, runner: CliRunner):
        """cli --help output contains 'sempath'."""
        result = runner.invoke(cli, ["--help"])
        assert "sempath" in result.output.lower()


class TestFindHelp:
    """Tests for the 'find' subcommand help."""

    def test_find_help_exits_0(self, runner: CliRunner):
        """find --help exits with code 0."""
        result = runner.invoke(cli, ["find", "--help"])
        assert result.exit_code == 0

    def test_find_help_shows_root_option(self, runner: CliRunner):
        """find --help shows --root option."""
        result = runner.invoke(cli, ["find", "--help"])
        assert "--root" in result.output

    def test_find_help_shows_depth_option(self, runner: CliRunner):
        """find --help shows --depth option."""
        result = runner.invoke(cli, ["find", "--help"])
        assert "--depth" in result.output

    def test_find_help_shows_min_confidence_option(self, runner: CliRunner):
        """find --help shows --min-confidence option."""
        result = runner.invoke(cli, ["find", "--help"])
        assert "--min-confidence" in result.output

    def test_find_help_shows_top_n_option(self, runner: CliRunner):
        """find --help shows --top-n option."""
        result = runner.invoke(cli, ["find", "--help"])
        assert "--top-n" in result.output

    def test_find_help_shows_non_interactive_option(self, runner: CliRunner):
        """find --help shows --non-interactive option."""
        result = runner.invoke(cli, ["find", "--help"])
        assert "--non-interactive" in result.output

    def test_find_help_shows_no_index_option(self, runner: CliRunner):
        """find --help shows --no-index option."""
        result = runner.invoke(cli, ["find", "--help"])
        assert "--no-index" in result.output

    def test_find_help_shows_json_option(self, runner: CliRunner):
        """find --help shows --json option."""
        result = runner.invoke(cli, ["find", "--help"])
        assert "--json" in result.output

    def test_find_help_shows_verbose_option(self, runner: CliRunner):
        """find --help shows --verbose option."""
        result = runner.invoke(cli, ["find", "--help"])
        assert "--verbose" in result.output


class TestAliasHelp:
    """Tests for the 'alias' subcommand group help."""

    def test_alias_help_exits_0(self, runner: CliRunner):
        """alias --help exits with code 0."""
        result = runner.invoke(cli, ["alias", "--help"])
        assert result.exit_code == 0


class TestIndexHelp:
    """Tests for the 'index' subcommand group help."""

    def test_index_help_exits_0(self, runner: CliRunner):
        """index --help exits with code 0."""
        result = runner.invoke(cli, ["index", "--help"])
        assert result.exit_code == 0


class TestExportMemoryHelp:
    """Tests for the 'export-memory' command help."""

    def test_export_memory_help_exits_0(self, runner: CliRunner):
        """export-memory --help exits with code 0."""
        result = runner.invoke(cli, ["export-memory", "--help"])
        assert result.exit_code == 0


class TestImportMemoryHelp:
    """Tests for the 'import-memory' command help."""

    def test_import_memory_help_exits_0(self, runner: CliRunner):
        """import-memory --help exits with code 0."""
        result = runner.invoke(cli, ["import-memory", "--help"])
        assert result.exit_code == 0


class TestConfigVerbose:
    """Tests for the 'config verbose' subcommand."""

    def test_config_verbose_help_exits_0(self, runner: CliRunner):
        """config verbose --help exits with code 0."""
        result = runner.invoke(cli, ["config", "verbose", "--help"])
        assert result.exit_code == 0

    def test_config_verbose_off(self, runner: CliRunner):
        """config verbose off disables verbosity in loaded config."""
        result = runner.invoke(cli, ["config", "verbose", "off"])
        assert result.exit_code == 0
        assert "disabled" in result.output

        from sempath.config import load_config

        cfg = load_config()
        assert cfg["verbose"] is False

    def test_config_verbose_on(self, runner: CliRunner):
        """config verbose on enables verbosity in loaded config."""
        result = runner.invoke(cli, ["config", "verbose", "on"])
        assert result.exit_code == 0
        assert "enabled" in result.output

        from sempath.config import load_config

        cfg = load_config()
        assert cfg["verbose"] is True


class TestConfigDepth:
    """Tests for the 'config depth' subcommand."""

    def test_config_depth_help_exits_0(self, runner: CliRunner):
        """config depth --help exits with code 0."""
        result = runner.invoke(cli, ["config", "depth", "--help"])
        assert result.exit_code == 0

    def test_config_depth_valid(self, runner: CliRunner):
        """config depth <N> updates depth in loaded config."""
        result = runner.invoke(cli, ["config", "depth", "10"])
        assert result.exit_code == 0
        assert "Default search depth set to 10" in result.output

        from sempath.config import load_config

        cfg = load_config()
        assert cfg["depth"] == 10

        # Reset depth to default 5 to prevent side-effects on other tests
        runner.invoke(cli, ["config", "depth", "5"])

    def test_config_depth_invalid(self, runner: CliRunner):
        """config depth with non-positive integer returns error."""
        result = runner.invoke(cli, ["config", "depth", "0"])
        assert result.exit_code != 0
        assert "Depth must be a positive integer" in result.output


def test_find_root_dir_leading_slash_normalization(tmp_path: Path):
    """Test that '/scratch' normalizes to local 'scratch' subdirectory."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    song = scratch / "song.mp3"
    song.write_text("audio content", encoding="utf-8")

    runner = CliRunner()
    # Invoke with '/scratch' relative to tmp_path context
    with runner.isolated_filesystem(temp_dir=tmp_path):
        sub_scratch = Path("scratch")
        sub_scratch.mkdir(exist_ok=True)
        (sub_scratch / "track.wav").write_text("wav content")

        res = runner.invoke(cli, ["find", "songs", "/scratch"])
        assert res.exit_code == 0
        assert "track.wav" in res.output
