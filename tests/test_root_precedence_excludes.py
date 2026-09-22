"""Root-precedence rules: an explicitly provided root bypasses index.exclude_patterns.

An explicit root (positional or ``--root``) means "scan here, trust me, see
everything": the search runs on-the-fly with full visibility, while the
persistent index is neither read nor mutated. A default root (not provided on
the command line) continues to honor ``index.exclude_patterns``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from click.testing import CliRunner

from sempath.cli import cli
from sempath.engine import SearchEngine


def _make_tree(root: Path) -> None:
    """Create a tree with a file buried inside an excluded 'build' subtree."""
    scratch = root / "build" / "CMakeFiles" / "CMakeScratch"
    scratch.mkdir(parents=True)
    (scratch / "note.txt").write_text("x", encoding="utf-8")
    (root / "README.md").write_text("y", encoding="utf-8")


class TestEngineRootPrecedence:
    """Engine-level behavior for the exclude_patterns override."""

    def _make_config(self, sample_config: dict) -> dict:
        cfg = copy.deepcopy(sample_config)
        cfg["index"]["exclude_patterns"] = ["build", "dist"]
        # Keep the test deterministic and fast: no H7/H8 model/LLM calls.
        cfg["handlers"]["enabled"] = ["h1", "h2", "h3", "h4", "h5", "h6"]
        return cfg

    def test_override_sees_excluded_subtree_and_never_touches_index(
        self, tmp_path: Path, sample_config: dict
    ) -> None:
        root = tmp_path / "proj"
        _make_tree(root)
        engine = SearchEngine(self._make_config(sample_config))

        # Explicit-root override (exclude_patterns=[]) scans on-the-fly:
        # the file under build/ is visible, and the index is left untouched.
        res = engine.find_path("note", root, depth=5, exclude_patterns=[], non_interactive=True)
        assert res.status == "success"
        assert res.match is not None
        assert res.match.path.name == "note.txt"
        assert "build" in res.match.path.parts
        assert not engine.index_manager.is_indexed(root.resolve())

    def test_default_keeps_excludes_and_uses_index(
        self, tmp_path: Path, sample_config: dict
    ) -> None:
        root = tmp_path / "proj"
        _make_tree(root)
        engine = SearchEngine(self._make_config(sample_config))

        # No override: config excludes apply, so the file under build/ is absent.
        res = engine.find_path("note", root, depth=5, non_interactive=True)
        assert res.status != "success"
        assert res.match is None
        # The default path does use the persistent index.
        assert engine.index_manager.is_indexed(root.resolve())


class TestCliRootPrecedence:
    """CLI-level behavior: explicit ROOT_DIR arg vs. default root."""

    def test_explicit_root_bypasses_exclude_patterns(self, tmp_path: Path) -> None:
        root = tmp_path / "proj"
        _make_tree(root)

        runner = CliRunner()
        result = runner.invoke(cli, ["find", "note", str(root), "--json", "--non-interactive"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["status"] == "success"
        assert (
            data["match"]["path"]
            .replace("\\", "/")
            .endswith("build/CMakeFiles/CMakeScratch/note.txt")
        )

    def test_default_root_still_respects_exclude_patterns(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = tmp_path / "proj"
        _make_tree(root)
        monkeypatch.chdir(root)

        runner = CliRunner()
        result = runner.invoke(cli, ["find", "note", "--json", "--non-interactive"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["status"] == "failed"
