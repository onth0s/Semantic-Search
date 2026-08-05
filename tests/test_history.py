"""Tests for last-search history: sempath list, sempath get N, and bare sempath N."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from sempath.cli import cli
from sempath.models import MatchResult, SearchResult
from sempath.utils.history import get_history_path, load_history, save_history


@pytest.fixture(autouse=True)
def _clean_history():
    """Remove any leftover snapshot so each test starts with an empty history."""
    history_path = get_history_path()
    if history_path.exists():
        history_path.unlink()
    yield


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click CliRunner instance."""
    return CliRunner()


@pytest.fixture
def real_paths(tmp_path: Path) -> list[Path]:
    """Create real files and return their paths in ranked order."""
    notes_dir = tmp_path / "Notes"
    notes_dir.mkdir()
    docs_dir = tmp_path / "Docs"
    docs_dir.mkdir()

    p1 = notes_dir / "notes.txt"
    p1.write_text("sample notes content", encoding="utf-8")
    p2 = notes_dir / "notes-old.txt"
    p2.write_text("older notes", encoding="utf-8")
    p3 = docs_dir / "readme.md"
    p3.write_text("# readme", encoding="utf-8")
    return [p1, p2, p3]


def _make_search_result(paths: list[Path]) -> SearchResult:
    """Return a SearchResult with primary path first, then near-misses."""
    return SearchResult(
        status="success",
        query="notes",
        match=MatchResult(paths[0], 0.95, "h4"),
        near_misses=[
            MatchResult(paths[1], 0.80, "h4"),
            MatchResult(paths[2], 0.70, "h6_alias"),
        ],
        message="",
        elapsed_seconds=0.5,
    )


def _write_history(paths: list[Path], root: Path | None = None) -> Path:
    """Persist a fake last-search snapshot and return its file path."""
    history_path = get_history_path()
    save_history(
        query="notes",
        root_dir=root or paths[0].parent,
        elapsed_seconds=0.5,
        search_result=_make_search_result(paths),
        path=history_path,
    )
    return history_path


@pytest.fixture
def patched_clipboard(monkeypatch) -> list[str]:
    """Patch history clipboard copy and record what was copied."""
    copied: list[str] = []

    def _fake_copy(text: str) -> bool:
        copied.append(text)
        return True

    monkeypatch.setattr("sempath.cli.history.copy_to_clipboard", _fake_copy)
    return copied


class TestHistoryStore:
    """Tests for the snapshot persistence layer."""

    def test_save_load_roundtrip(self, real_paths: list[Path]):
        """save_history persists matches primary-first with rank fields."""
        _write_history(real_paths)
        loaded = load_history()

        assert loaded is not None
        assert loaded["query"] == "notes"

        matches = loaded["matches"]
        assert [m["path"] for m in matches] == [str(p) for p in real_paths]
        assert [m["rank"] for m in matches] == [1, 2, 3]

    def test_load_history_missing_returns_none(self, tmp_path: Path):
        """load_history returns None when no snapshot exists."""
        assert load_history(tmp_path / "missing.json") is None

    def test_save_history_empty_result_writes_nothing(self, tmp_path: Path):
        """save_history skips writing when there are no matches."""
        empty = SearchResult(status="failed", query="x")
        path = tmp_path / "last_search.json"
        save_history("x", Path("."), 0.0, empty, path=path)
        assert not path.exists()


class TestListCommand:
    """Tests for the list command."""

    def test_list_no_history(self, runner: CliRunner):
        """list without a prior search exits 1 with a hint."""
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 1
        assert "No previous search found" in result.output

    def test_list_shows_numbered_matches(
        self, runner: CliRunner, real_paths: list[Path], patched_clipboard
    ):
        """list shows the query and 1-indexed matches from the last search."""
        _write_history(real_paths)
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "Last search" in result.output
        assert "notes" in result.output
        assert "1." in result.output
        assert "2." in result.output
        assert "3." in result.output
        for p in real_paths:
            assert p.name in result.output
        assert patched_clipboard == []

    def test_list_json(self, runner: CliRunner, real_paths: list[Path]):
        """list --json emits the matches array."""
        _write_history(real_paths)
        result = runner.invoke(cli, ["list", "--json"])
        assert result.exit_code == 0
        matches = json.loads(result.output)
        assert isinstance(matches, list)
        assert matches[0]["path"] == str(real_paths[0])


class TestGetCommand:
    """Tests for the get command."""

    def test_get_default_copies_top_match(
        self, runner: CliRunner, real_paths: list[Path], patched_clipboard
    ):
        """get with no N recalls the top match and copies it."""
        _write_history(real_paths)
        result = runner.invoke(cli, ["get"])
        assert result.exit_code == 0
        assert patched_clipboard == [str(real_paths[0])]
        assert "Match 1" in result.output
        assert "Copied to clipboard" in result.output

    def test_get_n_copies_match(self, runner: CliRunner, real_paths: list[Path], patched_clipboard):
        """get N copies the Nth match path."""
        _write_history(real_paths)
        result = runner.invoke(cli, ["get", "2"])
        assert result.exit_code == 0
        assert patched_clipboard == [str(real_paths[1])]
        assert "Match 2" in result.output

    def test_get_no_history(self, runner: CliRunner, patched_clipboard):
        """get without a prior search exits 1."""
        result = runner.invoke(cli, ["get", "1"])
        assert result.exit_code == 1
        assert "No previous search found" in result.output
        assert patched_clipboard == []

    def test_get_invalid_rank(self, runner: CliRunner, real_paths: list[Path], patched_clipboard):
        """get with an out-of-range rank exits 1 and copies nothing."""
        _write_history(real_paths)
        result = runner.invoke(cli, ["get", "99"])
        assert result.exit_code == 1
        assert "Invalid rank" in result.output
        assert patched_clipboard == []

    def test_get_no_copy(self, runner: CliRunner, real_paths: list[Path], patched_clipboard):
        """get --no-copy skips the clipboard and says so."""
        _write_history(real_paths)
        result = runner.invoke(cli, ["get", "1", "--no-copy"])
        assert result.exit_code == 0
        assert patched_clipboard == []
        assert "clipboard copy skipped" in result.output

    def test_get_json(self, runner: CliRunner, real_paths: list[Path], patched_clipboard):
        """get N --json emits the raw match record."""
        _write_history(real_paths)
        result = runner.invoke(cli, ["get", "3", "--json"])
        assert result.exit_code == 0
        match = json.loads(result.output)
        assert match["path"] == str(real_paths[2])
        assert match["rank"] == 3

    def test_get_missing_path_warns(self, runner: CliRunner, real_paths: list[Path], tmp_path):
        """get warns and exits 1 when the stored path no longer exists."""
        gone = tmp_path / "gone.txt"
        _write_history([gone, real_paths[1], real_paths[2]], root=tmp_path)
        result = runner.invoke(cli, ["get", "1", "--no-copy"])
        assert result.exit_code == 1
        assert "no longer exists" in result.output


class TestBareNumberShorthand:
    """Tests for the bare 'sempath N' shorthand routing."""

    def test_bare_number_is_lean_get(
        self, runner: CliRunner, real_paths: list[Path], patched_clipboard
    ):
        """sempath 2 prints the raw path and copies it to the clipboard."""
        _write_history(real_paths)
        result = runner.invoke(cli, ["2"])
        assert result.exit_code == 0
        assert result.output.strip() == str(real_paths[1])
        assert patched_clipboard == [str(real_paths[1])]

    def test_bare_number_without_history(self, runner: CliRunner, patched_clipboard):
        """sempath 1 without a prior search exits 1."""
        result = runner.invoke(cli, ["1"])
        assert result.exit_code == 1
        assert patched_clipboard == []


class TestFindPersistsHistory:
    """Tests that a real search writes the snapshot used by list/get."""

    def test_find_then_list_e2e(self, runner: CliRunner, mock_fs_path: Path, monkeypatch):
        """A successful find is recalled by list and get."""
        monkeypatch.setattr("sempath.cli.find.copy_to_clipboard", lambda text: True)
        monkeypatch.setattr("sempath.cli.history.copy_to_clipboard", lambda text: True)

        res_find = runner.invoke(cli, ["find", "notes", str(mock_fs_path)])
        assert res_find.exit_code == 0

        res_list = runner.invoke(cli, ["list"])
        assert res_list.exit_code == 0
        assert "Last search" in res_list.output
        assert "notes.txt" in res_list.output

        res_get = runner.invoke(cli, ["1"])
        assert res_get.exit_code == 0
        assert "notes.txt" in res_get.output
