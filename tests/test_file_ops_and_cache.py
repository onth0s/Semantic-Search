"""Tests for file_ops, stat_cache, and config_schema."""

from __future__ import annotations

from pathlib import Path

from sempath.config_schema import AppConfig
from sempath.utils.file_ops import (
    extract_matching_snippets,
    format_human_size,
    get_path_file_meta,
    is_text_file,
    read_text_safely,
)
from sempath.utils.stat_cache import FileStatCache


def test_format_human_size_exact_two_decimals():
    """Verify sizes are formatted with exactly 2 decimal places per project rules."""
    assert format_human_size(500) == "500.00 B"
    assert format_human_size(1024) == "1.00 KB"
    assert format_human_size(1536) == "1.50 KB"
    assert format_human_size(1048576) == "1.00 MB"
    assert format_human_size(1073741824) == "1.00 GB"


def test_file_ops_text_detection_and_snippets(tmp_path: Path):
    """Test text file detection, safe reading, and snippet extraction."""
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text(
        "line one\nfind this key word\nline three\nkey word again\n",
        encoding="utf-8",
    )

    assert is_text_file(txt_file) is True
    content = read_text_safely(txt_file)
    assert content is not None
    assert "find this key word" in content

    snippets = extract_matching_snippets(content, "key word")
    assert len(snippets) == 2
    assert snippets[0] == (2, "find this key word")
    assert snippets[1] == (4, "key word again")

    meta = get_path_file_meta(txt_file)
    assert "B" in meta or "KB" in meta

    # Binary file
    bin_file = tmp_path / "binary.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03\xff")
    assert is_text_file(bin_file) is False
    assert read_text_safely(bin_file) is None


def test_stat_cache(tmp_path: Path):
    """Test FileStatCache behavior."""
    file1 = tmp_path / "f1.txt"
    file1.write_text("abc", encoding="utf-8")

    cache = FileStatCache()
    st1 = cache.get_stat(file1)
    assert st1 is not None
    assert cache.get_size(file1) == 3
    assert cache.get_mtime(file1) > 0

    # Ensure cached lookup
    assert cache.get_stat(file1) is st1

    cache.clear()
    assert cache.get_stat(tmp_path / "nonexistent.txt") is None


def test_config_schema_roundtrip():
    """Test AppConfig serialization and deserialization."""
    cfg = AppConfig()
    d = cfg.to_dict()
    assert isinstance(d, dict)
    assert d["depth"] == 5
    assert "h1" in d["handlers"]["enabled"]

    reloaded = AppConfig.from_dict(d)
    assert reloaded.depth == cfg.depth
    assert reloaded.handlers.enabled == cfg.handlers.enabled
