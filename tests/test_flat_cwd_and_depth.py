"""Tests for flat CWD search (./), --depth -1, and --full-depth options."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from sempath.cli import cli


def test_flat_cwd_search_with_dot_slash(tmp_path: Path):
    """Verify that ./ or .\\ searches ONLY flat CWD, ignoring subdirectories."""
    # Setup files in cwd and in subdirectories
    file_cwd = tmp_path / "target_flat.txt"
    file_cwd.write_text("content flat", encoding="utf-8")

    sub_dir = tmp_path / "subfolder"
    sub_dir.mkdir()
    file_sub = sub_dir / "target_nested.txt"
    file_sub.write_text("content nested", encoding="utf-8")

    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        (Path.cwd() / "target_flat.txt").write_text("content flat", encoding="utf-8")
        sub = Path.cwd() / "subfolder"
        sub.mkdir()
        (sub / "target_nested.txt").write_text("content nested", encoding="utf-8")

        # 1. Search with ./ -> should ONLY find target_flat.txt
        res_dot_slash = runner.invoke(cli, ["find", "target", "./", "--json"])
        assert res_dot_slash.exit_code == 0
        data_dot_slash = json.loads(res_dot_slash.output)
        matches = []
        if data_dot_slash.get("match"):
            matches.append(data_dot_slash["match"]["path"])
        for nm in data_dot_slash.get("near_misses", []):
            matches.append(nm["path"])

        assert any("target_flat.txt" in m for m in matches)
        assert not any("target_nested.txt" in m for m in matches)

        # 2. Search with .\\ -> should also ONLY find flat files
        res_backslash = runner.invoke(cli, ["find", "target", ".\\", "--json"])
        assert res_backslash.exit_code == 0
        data_backslash = json.loads(res_backslash.output)
        matches_bs = []
        if data_backslash.get("match"):
            matches_bs.append(data_backslash["match"]["path"])
        for nm in data_backslash.get("near_misses", []):
            matches_bs.append(nm["path"])

        assert any("target_flat.txt" in m for m in matches_bs)
        assert not any("target_nested.txt" in m for m in matches_bs)

        # 3. Search with . (recursive) -> should find both
        res_dot = runner.invoke(cli, ["find", "target", ".", "--json"])
        assert res_dot.exit_code == 0
        data_dot = json.loads(res_dot.output)
        matches_dot = []
        if data_dot.get("match"):
            matches_dot.append(data_dot["match"]["path"])
        for nm in data_dot.get("near_misses", []):
            matches_dot.append(nm["path"])

        assert any("target_flat.txt" in m for m in matches_dot)
        assert any("target_nested.txt" in m for m in matches_dot)


def test_full_depth_and_negative_one(tmp_path: Path):
    """Verify --full-depth and --depth -1 traverse arbitrarily deep subdirectories."""
    runner = CliRunner()
    index_cache_dir = tmp_path / "isolated_index_cache"
    index_cache_dir.mkdir()

    with (
        patch("sempath.engine.get_index_store_path", return_value=index_cache_dir),
        patch("sempath.config.get_index_store_path", return_value=index_cache_dir),
        runner.isolated_filesystem(temp_dir=tmp_path),
    ):
        # Create a deep 8-level tree
        deep_dir = Path.cwd()
        for i in range(8):
            deep_dir = deep_dir / f"level{i}"
            deep_dir.mkdir()
        deep_file = deep_dir / "deep_target.txt"
        deep_file.write_text("deep", encoding="utf-8")

        # 1. Default depth (5) -> should NOT find deep_target.txt (depth=8)
        res_default = runner.invoke(
            cli, ["find", "deep_target", ".", "--non-interactive", "--json"]
        )
        data_default = json.loads(res_default.output)
        assert data_default["status"] in ("failed", "ambiguous")

        # 2. --full-depth -> SHOULD find deep_target.txt
        res_full = runner.invoke(
            cli, ["find", "deep_target", ".", "--full-depth", "--non-interactive", "--json"]
        )
        assert res_full.exit_code == 0
        data_full = json.loads(res_full.output)
        assert data_full["status"] == "success"
        assert "deep_target.txt" in data_full["match"]["path"]

        # 3. --depth -1 -> SHOULD find deep_target.txt
        res_neg1 = runner.invoke(
            cli, ["find", "deep_target", ".", "--depth", "-1", "--non-interactive", "--json"]
        )
        assert res_neg1.exit_code == 0
        data_neg1 = json.loads(res_neg1.output)
        assert data_neg1["status"] == "success"
        assert "deep_target.txt" in data_neg1["match"]["path"]
