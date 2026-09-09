"""Candidate filtering and sorting pipeline.

Provides decoupled functions for applying heuristics constraints
(extensions, age, types) and sorting strategies to candidate paths and MatchResults.
"""

from __future__ import annotations

import fnmatch
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sempath.models import MatchResult
    from sempath.utils.stat_cache import FileStatCache


def filter_by_intent(candidates: list[Path], directory_only: bool, file_only: bool) -> list[Path]:
    """Filter candidates based on directory or file intent."""
    if directory_only:
        return [p for p in candidates if p.is_dir()]
    if file_only:
        return [p for p in candidates if p.is_file()]
    return candidates


def filter_by_extensions(candidates: list[Path], exts: list[str]) -> list[Path]:
    """Filter candidates by a list of extensions (supports wildcards)."""
    if not exts:
        return candidates

    filtered = []
    for p in candidates:
        suffix = p.suffix.lower().lstrip(".")
        matched = False
        for ext_pat in exts:
            if fnmatch.fnmatch(suffix, ext_pat.lower()):
                matched = True
                break
        if matched:
            filtered.append(p)
    return filtered


def filter_by_age(
    candidates: list[Path],
    max_age_seconds: int | None,
    stat_cache: FileStatCache | None = None,
) -> list[Path]:
    """Filter candidates to keep only those modified within max_age_seconds."""
    if max_age_seconds is None:
        return candidates

    now = time.time()
    valid_candidates = []
    for p in candidates:
        mtime = stat_cache.get_mtime(p) if stat_cache is not None else get_path_mtime(p)
        if mtime > 0.0 and (now - mtime <= max_age_seconds):
            valid_candidates.append(p)
    return valid_candidates


def get_path_mtime(p: Path, stat_cache: FileStatCache | None = None) -> float:
    """Safely get modification time of a path, defaulting to 0.0 on error."""
    if stat_cache is not None:
        return stat_cache.get_mtime(p)
    try:
        return p.stat().st_mtime
    except (OSError, PermissionError):
        return 0.0


def get_path_size(p: Path, stat_cache: FileStatCache | None = None) -> int:
    """Safely get file size of a path, returning 0 if directory or on error."""
    if stat_cache is not None:
        return stat_cache.get_size(p)
    try:
        return p.stat().st_size if p.is_file() else 0
    except (OSError, PermissionError):
        return 0


def _size_for_smallest(p: Path, stat_cache: FileStatCache | None = None) -> float:
    """Helper to return path size, defaulting to infinity for dirs or errors."""
    if stat_cache is not None:
        st = stat_cache.get_stat(p)
        if st is not None and not p.is_dir():
            return float(st.st_size)
        return float("inf")
    try:
        return float(p.stat().st_size) if p.is_file() else float("inf")
    except (OSError, PermissionError):
        return float("inf")


def _mtime_for_oldest(p: Path, stat_cache: FileStatCache | None = None) -> float:
    """Helper to return path mtime, defaulting to infinity on error."""
    if stat_cache is not None:
        st = stat_cache.get_stat(p)
        return float(st.st_mtime) if st is not None else float("inf")
    try:
        return p.stat().st_mtime
    except (OSError, PermissionError):
        return float("inf")


def sort_candidates(
    candidates: list[Path],
    latest: bool,
    largest: bool,
    smallest: bool,
    oldest: bool,
    stat_cache: FileStatCache | None = None,
) -> None:
    """Sort candidates in-place by modification time or size."""
    if latest:
        candidates.sort(key=lambda p: get_path_mtime(p, stat_cache=stat_cache), reverse=True)
    elif largest:
        candidates.sort(key=lambda p: get_path_size(p, stat_cache=stat_cache), reverse=True)
    elif smallest:
        candidates.sort(key=lambda p: _size_for_smallest(p, stat_cache=stat_cache))
    elif oldest:
        candidates.sort(key=lambda p: _mtime_for_oldest(p, stat_cache=stat_cache))


def sort_match_results(
    matches: list[MatchResult],
    latest: bool = False,
    largest: bool = False,
    smallest: bool = False,
    oldest: bool = False,
    stat_cache: FileStatCache | None = None,
) -> None:
    """Sort MatchResult objects in-place based on ordering flags or confidence descending."""
    if latest:
        matches.sort(key=lambda m: (-get_path_mtime(m.path, stat_cache=stat_cache), -m.confidence))
    elif largest:
        matches.sort(key=lambda m: (-get_path_size(m.path, stat_cache=stat_cache), -m.confidence))
    elif smallest:
        matches.sort(
            key=lambda m: (_size_for_smallest(m.path, stat_cache=stat_cache), -m.confidence)
        )
    elif oldest:
        matches.sort(
            key=lambda m: (_mtime_for_oldest(m.path, stat_cache=stat_cache), -m.confidence)
        )
    else:
        matches.sort(key=lambda m: (-m.confidence, -len(m.snippets), len(m.path.parts)))
