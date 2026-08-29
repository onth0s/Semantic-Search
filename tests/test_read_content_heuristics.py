"""Content search (--read-content) combined with heuristics: extension token + sort word."""

from __future__ import annotations

import os
from pathlib import Path

from sempath.engine import SearchEngine


def test_read_content_with_extension_and_sort_uses_content(tmp_path: Path, sample_config: dict):
    """-c '.yaml latest' must grep content, not match actual .yaml files by extension."""
    engine = SearchEngine(sample_config)

    # A real .yaml file whose text contains NO '.yaml' substring.
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("key: value\nversion: 1\n", encoding="utf-8")

    # A .md file whose text mentions 'yaml'; made newer so it wins on 'latest'.
    md_file = tmp_path / "notes.md"
    md_file.write_text("These notes discuss settings.yaml parsing.\n", encoding="utf-8")

    # Force md_file to be the newest.
    old = yaml_file.stat().st_mtime - 100
    os.utime(yaml_file, (old, old))

    res = engine.find_path(".yaml latest", tmp_path, no_index=True, read_content=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.handler == "content_search"
    assert res.match.path == md_file


def test_read_content_with_extension_only_keeps_content(tmp_path: Path, sample_config: dict):
    """-c '.yaml' still greps content even when the extension token is present."""
    engine = SearchEngine(sample_config)

    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("key: value\nversion: 1\n", encoding="utf-8")

    md_file = tmp_path / "notes.md"
    md_file.write_text("These notes discuss settings.yaml parsing.\n", encoding="utf-8")

    res = engine.find_path(".yaml", tmp_path, no_index=True, read_content=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.handler == "content_search"
    assert res.match.path == md_file


def test_read_content_with_only_sort_word_falls_back_to_mtime_sort(
    tmp_path: Path, sample_config: dict
):
    """-c 'latest' strips to an empty pattern and falls back to mtime sort (explicit_flags)."""
    engine = SearchEngine(sample_config)

    older = tmp_path / "older.txt"
    older.write_text("one\n", encoding="utf-8")
    newer = tmp_path / "newer.txt"
    newer.write_text("two\n", encoding="utf-8")

    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    res = engine.find_path("latest", tmp_path, no_index=True, read_content=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.handler == "explicit_flags"
    assert res.match.path == newer


def test_read_content_with_sort_orders_content_by_mtime(tmp_path: Path, sample_config: dict):
    """Multiple content matches for '.yaml content' are returned newest-first."""
    engine = SearchEngine(sample_config)

    a = tmp_path / "a.md"
    a.write_text("contains yaml here\n", encoding="utf-8")
    b = tmp_path / "b.md"
    b.write_text("also yaml here\n", encoding="utf-8")

    # Make a older than b, so 'latest' should prefer b.
    os.utime(a, (1000, 1000))
    os.utime(b, (2000, 2000))

    res = engine.find_path("yaml latest", tmp_path, no_index=True, read_content=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.handler == "content_search"
    assert res.match.path == b
