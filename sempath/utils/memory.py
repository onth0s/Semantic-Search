"""Memory utility for sempath.

Manages the persistent learned_aliases.yaml file, calculating decay rankings,
supporting chronological undo stack operations, and handling import/export of memory.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import yaml


def get_memory_file_path() -> Path:
    """Return the absolute Path to learned_aliases.yaml."""
    appdata = os.environ.get("APPDATA")
    base_dir = Path(appdata) / "sempath" if appdata else Path.home() / ".config" / "sempath"

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "learned_aliases.yaml"


def calculate_decay_rank(hits: int, timestamp_str: str) -> float:
    """Calculate the decay rank based on hits and recency (7-day half-life)."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
    except Exception:
        dt = datetime.now(UTC)

    now = datetime.now(UTC)
    delta = now - dt
    days_elapsed = max(0.0, delta.total_seconds() / 86400.0)

    # Formula: hits * 0.5 ^ (days / 7)
    decay_rank = hits * (0.5 ** (days_elapsed / 7.0))
    return round(decay_rank, 4)


def _memory_sort_key(entry: dict) -> tuple[float, int, str]:
    """Helper to return sorting key for memory entries (decay_rank, hits, query)."""
    return (entry.get("decay_rank", 0.0), entry.get("hits", 0), entry.get("query", ""))


def load_memory(path: Path | None = None) -> list[dict]:
    """Load and return the list of learned memory entries, sorted by decay rank."""
    filepath = path or get_memory_file_path()
    if not filepath.exists():
        return []

    try:
        with open(filepath, encoding="utf-8") as f:
            entries = yaml.safe_load(f)
            if not isinstance(entries, list):
                return []
    except Exception:
        return []

    # Recalculate decay rank dynamically for all entries
    for entry in entries:
        if isinstance(entry, dict) and "hits" in entry and "timestamp" in entry:
            entry["decay_rank"] = calculate_decay_rank(entry["hits"], entry["timestamp"])

    # Sort descending by decay rank, then by hits, then alphabetically by query
    entries.sort(key=_memory_sort_key, reverse=True)
    return entries


def save_memory(entries: list[dict], path: Path | None = None) -> None:
    """Save the memory entries list to YAML file."""
    filepath = path or get_memory_file_path()
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Clean entries structure
    cleaned = []
    for e in entries:
        cleaned.append(
            {
                "query": e.get("query", ""),
                "path": str(e.get("path", "")),
                "timestamp": e.get("timestamp", ""),
                "hits": int(e.get("hits", 1)),
                "decay_rank": float(e.get("decay_rank", 0.0)),
            }
        )

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(cleaned, f, default_flow_style=False, sort_keys=False)
    except Exception:
        pass


def add_or_update_memory(query: str, target_path: str | Path, path: Path | None = None) -> None:
    """Add a new confirmation or update hits/timestamp of an existing learned alias."""
    entries = load_memory(path)
    now_str = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    target_path_str = str(Path(target_path).resolve())
    query_clean = query.strip()

    # Look for existing match
    found = False
    for entry in entries:
        if (
            entry.get("query", "").lower() == query_clean.lower()
            and str(Path(entry.get("path", "")).resolve()) == target_path_str
        ):
            entry["hits"] = entry.get("hits", 0) + 1
            entry["timestamp"] = now_str
            found = True
            break

    if not found:
        entries.append(
            {
                "query": query_clean,
                "path": target_path_str,
                "timestamp": now_str,
                "hits": 1,
                "decay_rank": 1.0,
            }
        )

    # Recalculate, sort and save
    for entry in entries:
        entry["decay_rank"] = calculate_decay_rank(entry["hits"], entry["timestamp"])

    entries.sort(key=_memory_sort_key, reverse=True)
    save_memory(entries, path)


def undo_last_memory(path: Path | None = None) -> dict | None:
    """Remove and return the chronologically last added/updated learned alias."""
    entries = load_memory(path)
    if not entries:
        return None

    # Find the one with the newest timestamp
    newest_entry = None
    newest_dt = None
    newest_idx = -1

    for idx, entry in enumerate(entries):
        t_str = entry.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
        except Exception:
            continue

        if newest_dt is None or dt > newest_dt:
            newest_dt = dt
            newest_entry = entry
            newest_idx = idx

    if newest_entry is not None:
        entries.pop(newest_idx)
        save_memory(entries, path)
        return newest_entry

    return None


def merge_memory_files(source_path: Path, dest_path: Path | None = None) -> None:
    """Merge an external memory file into the local learned_aliases.yaml."""
    dest_path = dest_path or get_memory_file_path()
    dest_entries = load_memory(dest_path)
    source_entries = load_memory(source_path)

    # Index destination entries by query + path for easy merging
    dest_map = {}
    for entry in dest_entries:
        key = (entry.get("query", "").lower(), str(Path(entry.get("path", "")).resolve()))
        dest_map[key] = entry

    for src_entry in source_entries:
        key = (src_entry.get("query", "").lower(), str(Path(src_entry.get("path", "")).resolve()))
        if key in dest_map:
            dest_entry = dest_map[key]
            # Accumulate hits
            dest_entry["hits"] = dest_entry.get("hits", 0) + src_entry.get("hits", 1)
            # Take the newest timestamp
            try:
                t_dest = dest_entry.get("timestamp", "").replace("Z", "+00:00")
                t_src = src_entry.get("timestamp", "").replace("Z", "+00:00")
                dt_dest = datetime.fromisoformat(t_dest)
                dt_src = datetime.fromisoformat(t_src)
                if dt_src > dt_dest:
                    dest_entry["timestamp"] = src_entry.get("timestamp", "")
            except Exception:
                pass
        else:
            dest_entries.append(src_entry)

    # Recalculate rankings and save
    for entry in dest_entries:
        entry["decay_rank"] = calculate_decay_rank(entry["hits"], entry["timestamp"])

    dest_entries.sort(key=_memory_sort_key, reverse=True)
    save_memory(dest_entries, dest_path)
