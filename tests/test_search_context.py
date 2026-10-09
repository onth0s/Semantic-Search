"""Unit tests for SearchContext."""

from __future__ import annotations

from pathlib import Path

from sempath.search_context import SearchContext


def test_search_context_get_path_stat(tmp_path: Path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("hello", encoding="utf-8")

    ctx = SearchContext(raw_query="sample", search_root=tmp_path)
    mtime, size, is_file = ctx.get_path_stat(test_file)

    assert is_file is True
    assert size == 5
    assert mtime > 0.0

    # Ensure caching works
    assert test_file in ctx.metadata_cache
    mtime2, size2, is_file2 = ctx.get_path_stat(test_file)
    assert (mtime2, size2, is_file2) == (mtime, size, is_file)


def test_search_context_missing_file(tmp_path: Path):
    missing_file = tmp_path / "nonexistent.txt"
    ctx = SearchContext(raw_query="missing", search_root=tmp_path)
    mtime, size, is_file = ctx.get_path_stat(missing_file)
    assert is_file is False
    assert size == 0
    assert mtime == 0.0
