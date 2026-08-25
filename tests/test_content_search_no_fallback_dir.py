"""Unit tests: content search (-c) does not fall back to directory content matches."""

from __future__ import annotations

from pathlib import Path

from sempath.engine import SearchEngine


def test_content_search_fails_cleanly_when_not_found(sample_config: dict, tmp_path: Path):
    """When searching content for '500ms' and no file contains it, do not match parent directory."""
    engine = SearchEngine(sample_config)

    # Structure: tmp_path / "00__DEV" / "AutoHotkey" / "src" / "00_header.ahk"
    dev_dir = tmp_path / "00__DEV"
    src_dir = dev_dir / "AutoHotkey" / "src"
    src_dir.mkdir(parents=True)

    f1 = src_dir / "00_header.ahk"
    f1.write_text("; AutoHotkey Header\n#SingleInstance Force\n", encoding="utf-8")
    f2 = src_dir / "10_serial.ahk"
    f2.write_text("; Serial communication\nbaud := 9600\n", encoding="utf-8")

    res = engine.find_path("500ms", src_dir, no_index=True, read_content=True)
    assert res.status in ("ambiguous", "failed")
    # Must not return directory_content_match for 00__DEV
    if res.match:
        assert res.match.handler != "directory_content_match"
    for nm in res.near_misses:
        assert nm.handler != "directory_content_match"


def test_content_search_finds_actual_content(sample_config: dict, tmp_path: Path):
    """When searching content for '500ms' and a file contains it, return the matching file."""
    engine = SearchEngine(sample_config)

    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)

    f1 = src_dir / "timing.ahk"
    f1.write_text("Sleep, 500ms ; wait 500 milliseconds\n", encoding="utf-8")

    res = engine.find_path("500ms", src_dir, no_index=True, read_content=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path == f1
    assert res.match.handler == "content_search"
    assert len(res.match.snippets) > 0
