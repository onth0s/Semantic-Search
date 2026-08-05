"""Last-search snapshot store for sempath.

Persists the ranked results of the most recent search to
``%APPDATA%\\sempath\\last_search.json`` so that ``sempath list``,
``sempath get N``, and bare ``sempath N`` can recall matches without
re-running an expensive search.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sempath.models import SearchResult


def get_history_path() -> Path:
    """Return the absolute Path to last_search.json."""
    appdata = os.environ.get("APPDATA")
    base_dir = Path(appdata) / "sempath" if appdata else Path.home() / ".config" / "sempath"

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "last_search.json"


def history_matches(history: dict | None) -> list[dict]:
    """Return the ranked matches list of a history snapshot (empty if none)."""
    if not history:
        return []
    matches = history.get("matches", [])
    return matches if isinstance(matches, list) else []


def load_history(path: Path | None = None) -> dict | None:
    """Load and return the last search snapshot, or None if missing/corrupt."""
    filepath = path or get_history_path()
    if not filepath.exists():
        return None

    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("matches", []), list):
            return None
        return data
    except (OSError, ValueError):
        return None


def save_history(
    query: str,
    root_dir: Path,
    elapsed_seconds: float,
    search_result: SearchResult,
    path: Path | None = None,
) -> None:
    """Persist a search snapshot with the primary match ranked first.

    Args:
        query: The original search query.
        root_dir: The search root directory.
        elapsed_seconds: Total search time in seconds.
        search_result: The result object to snapshot.
        path: Optional explicit history file path (for tests).
    """
    matches: list[dict] = []

    def _append_match(m: Any, rank: int) -> None:
        entry: dict[str, Any] = {
            "path": str(m.path),
            "confidence": float(m.confidence),
            "handler": m.handler,
            "rank": rank,
        }
        snippets = getattr(m, "snippets", ())
        if snippets:
            entry["snippets"] = [[int(ln), str(text)] for ln, text in snippets]
        matches.append(entry)

    if search_result.match is not None:
        _append_match(search_result.match, 1)
    for rank, nm in enumerate(search_result.near_misses, start=len(matches) + 1):
        _append_match(nm, rank)

    if not matches:
        return

    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    snapshot = {
        "query": query,
        "timestamp": timestamp,
        "root": str(Path(root_dir).resolve()),
        "elapsed_seconds": round(float(elapsed_seconds), 4),
        "matches": matches,
    }

    filepath = path or get_history_path()
    filepath.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
