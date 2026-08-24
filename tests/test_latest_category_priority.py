"""Unit tests for category/modifier priority in filenames and latest modifier query sorting."""

from __future__ import annotations

import os
import time
from pathlib import Path

from sempath.engine import SearchEngine
from sempath.heuristics import extract_heuristics


def test_heuristics_compound_latest_modifier():
    """Query 'formal_verification_latest-latest' sets latest=True and retains stem."""
    res = extract_heuristics("formal_verification_latest-latest")
    assert res.latest is True
    # The clean_query and name_query should retain the remaining 'formal verification latest' tokens
    assert "latest" in res.clean_query
    assert "formal" in res.clean_query
    assert "verification" in res.clean_query


def test_filename_category_priority_and_sorting(sample_config: dict, tmp_path: Path):
    """Test filename priority with 'latest' in name vs modifier query 'latest-latest'."""
    engine = SearchEngine(sample_config)

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True)

    # Create files with specific timestamps
    f_old = logs_dir / "formal_verification_2026-08-24T14-03-03Z.log"
    f_mid1 = logs_dir / "formal_verification_2026-08-24T14-28-34Z.log"
    f_mid2 = logs_dir / "formal_verification_2026-08-24T14-29-16Z.log"
    f_latest_named = logs_dir / "formal_verification_latest.log"
    f_newest = logs_dir / "formal_verification_2026-08-24T14-32-18Z.log"

    base_time = time.time() - 3600
    for idx, f in enumerate([f_old, f_mid1, f_mid2, f_latest_named, f_newest]):
        f.write_text(f"content {idx}")
        mtime = base_time + (idx * 60)
        os.utime(f, (mtime, mtime))

    # 1. Query 'formal_verification_latest' extracts 'latest=True' with
    # clean_query='formal verification', returning the newest formal_verification log (f_newest).
    res1 = engine.find_path("formal_verification_latest", tmp_path, no_index=True, top_n=5)
    assert res1.status == "success"
    assert res1.match is not None
    assert res1.match.path == f_newest

    # 2. Query 'formal_verification_latest-latest' extracts the modifier 'latest=True'
    # and keeps 'formal_verification_latest' as the clean query stem, sorting by latest mtime.
    res2 = engine.find_path("formal_verification_latest-latest", tmp_path, no_index=True, top_n=5)
    assert res2.status == "success"
    assert res2.match is not None
    assert res2.match.path == f_newest
    all_paths = [res2.match.path, *(nm.path for nm in res2.near_misses)]
    assert all_paths[0] == f_newest
    assert all_paths[1] == f_latest_named


def test_filename_with_category_tag_not_overridden(sample_config: dict, tmp_path: Path):
    """File named 'video_converter.py' or 'image_editor.rs' is matched directly when searched."""
    engine = SearchEngine(sample_config)

    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    f_code = src_dir / "video_converter.py"
    f_code.write_text("print('video')")

    res = engine.find_path("video_converter", tmp_path, no_index=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path == f_code
