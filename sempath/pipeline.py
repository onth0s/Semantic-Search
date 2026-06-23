"""Candidate filtering and sorting pipeline.

Provides decoupled functions for applying heuristics constraints
(extensions, age, types) and sorting strategies to candidate paths.
"""

from __future__ import annotations

import fnmatch
import time
from pathlib import Path


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


def filter_by_age(candidates: list[Path], max_age_seconds: int | None) -> list[Path]:
    """Filter candidates to keep only those modified within max_age_seconds."""
    if max_age_seconds is None:
        return candidates

    now = time.time()
    valid_candidates = []
    for p in candidates:
        try:
            if now - p.stat().st_mtime <= max_age_seconds:
                valid_candidates.append(p)
        except Exception:
            pass
    return valid_candidates


def sort_candidates(
    candidates: list[Path],
    latest: bool,
    largest: bool,
    smallest: bool,
    oldest: bool,
) -> None:
    """Sort candidates in-place by modification time or size."""
    if latest:

        def get_mtime(p: Path) -> float:
            try:
                return p.stat().st_mtime
            except Exception:
                return 0.0

        candidates.sort(key=get_mtime, reverse=True)

    elif largest:

        def get_size(p: Path) -> int:
            try:
                return p.stat().st_size if p.is_file() else 0
            except Exception:
                return 0

        candidates.sort(key=get_size, reverse=True)

    elif smallest:

        def get_size_smallest(p: Path) -> float:
            try:
                return float(p.stat().st_size) if p.is_file() else float("inf")
            except Exception:
                return float("inf")

        candidates.sort(key=get_size_smallest)

    elif oldest:

        def get_mtime_oldest(p: Path) -> float:
            try:
                return p.stat().st_mtime
            except Exception:
                return float("inf")

        candidates.sort(key=get_mtime_oldest)
