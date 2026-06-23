"""Unit tests for sempath.utils.memory — learned alias store and ranking."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sempath.utils.memory import (
    add_or_update_memory,
    calculate_decay_rank,
    load_memory,
    merge_memory_files,
    save_memory,
    undo_last_memory,
)


@pytest.fixture
def temp_memory_file(tmp_path: Path) -> Path:
    """Provide a path to a temporary memory YAML file."""
    return tmp_path / "learned_aliases.yaml"


def test_decay_rank_calculation():
    """calculate_decay_rank decreases as time passes."""
    now_str = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # 0 days elapsed -> full hits
    rank_now = calculate_decay_rank(10, now_str)
    assert rank_now == 10.0

    # 7 days elapsed -> half hits
    week_ago = datetime.now(UTC) - timedelta(days=7)
    week_ago_str = week_ago.isoformat().replace("+00:00", "Z")
    rank_week_ago = calculate_decay_rank(10, week_ago_str)
    assert rank_week_ago == 5.0

    # 14 days elapsed -> quarter hits
    two_weeks_ago = datetime.now(UTC) - timedelta(days=14)
    two_weeks_ago_str = two_weeks_ago.isoformat().replace("+00:00", "Z")
    rank_two_weeks_ago = calculate_decay_rank(10, two_weeks_ago_str)
    assert rank_two_weeks_ago == 2.5


def test_add_and_load_memory(temp_memory_file: Path):
    """Adding elements to memory stores them sorted by decay rank."""
    # Add first element
    add_or_update_memory("desktop/main", "C:/User/Desktop/__MAIN", temp_memory_file)
    entries = load_memory(temp_memory_file)
    assert len(entries) == 1
    assert entries[0]["query"] == "desktop/main"
    assert entries[0]["hits"] == 1

    # Add second element with different query
    add_or_update_memory("downloads", "C:/User/Downloads", temp_memory_file)
    entries = load_memory(temp_memory_file)
    assert len(entries) == 2

    # Add first element again -> hits should be 2
    add_or_update_memory("desktop/main", "C:/User/Desktop/__MAIN", temp_memory_file)
    entries = load_memory(temp_memory_file)
    assert len(entries) == 2
    assert entries[0]["query"] == "desktop/main"
    assert entries[0]["hits"] == 2


def test_undo_last_memory(temp_memory_file: Path):
    """undo_last_memory pops the latest added learned alias chronologically."""
    # Add two items with slightly different times
    now = datetime.now(UTC)
    t1 = (now - timedelta(seconds=10)).isoformat().replace("+00:00", "Z")
    t2 = now.isoformat().replace("+00:00", "Z")

    entries = [
        {"query": "old_query", "path": "C:/Old", "timestamp": t1, "hits": 1},
        {"query": "new_query", "path": "C:/New", "timestamp": t2, "hits": 1},
    ]
    save_memory(entries, temp_memory_file)

    # Undo should pop the newest one
    popped = undo_last_memory(temp_memory_file)
    assert popped is not None
    assert popped["query"] == "new_query"

    # Check remaining
    remaining = load_memory(temp_memory_file)
    assert len(remaining) == 1
    assert remaining[0]["query"] == "old_query"


def test_merge_memory_files(tmp_path: Path):
    """merge_memory_files aggregates hits and keeps latest timestamp."""
    src = tmp_path / "sempath.yaml"
    dest = tmp_path / "dest.yaml"

    t1 = (datetime.now(UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    t2 = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    src_entries = [
        {"query": "main", "path": "C:/Main", "timestamp": t2, "hits": 2},
        {"query": "other", "path": "C:/Other", "timestamp": t1, "hits": 1},
    ]
    dest_entries = [
        {"query": "main", "path": "C:/Main", "timestamp": t1, "hits": 1},
    ]

    save_memory(src_entries, src)
    save_memory(dest_entries, dest)

    merge_memory_files(src, dest)

    merged = load_memory(dest)
    # Total entries: main and other
    assert len(merged) == 2

    # 'main' should have 3 hits (2 from src + 1 from dest) and the latest timestamp (t2)
    main_entry = next(e for e in merged if e["query"] == "main")
    assert main_entry["hits"] == 3
    assert main_entry["timestamp"] == t2
