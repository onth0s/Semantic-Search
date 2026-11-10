"""Matching utilities for merging and manipulating MatchResult objects."""

from __future__ import annotations

import re

from sempath.models import MatchResult

COPY_STEM_RE = re.compile(r"\(\d+\)|\bcopy\b")


def match_tie_breaker_key(
    m: MatchResult, prefix: str = "", include_confidence: bool = False
) -> tuple:
    """Standard tie-breaker sort key for candidate matches.

    Prefers:
    1. Higher confidence (if include_confidence=True)
    2. Prefix matches (if prefix is non-empty)
    3. Canonical originals over copies ('copy', '(1)')
    4. Shallower directory depth (fewer path parts)
    5. Shorter stem length
    6. Alphabetical stem ordering
    """
    stem = m.path.stem.lower()
    is_copy = 1 if COPY_STEM_RE.search(stem) else 0
    prefix_dist = 0 if prefix and stem.startswith(prefix) else (1 if prefix else 0)
    if include_confidence:
        return (-m.confidence, prefix_dist, is_copy, len(m.path.parts), len(stem), stem)
    return (prefix_dist, is_copy, len(m.path.parts), len(stem), stem)


def merge_matches(existing: list[MatchResult], incoming: list[MatchResult]) -> list[MatchResult]:
    """Merge two lists of MatchResult objects, keeping higher confidence for duplicate paths.

    Args:
        existing: Initial list of match results.
        incoming: New list of match results to merge.

    Returns:
        Combined list of unique MatchResult objects sorted by highest confidence per path.
    """
    merged_map = {m.path: m for m in existing}
    for item in incoming:
        if item.path in merged_map:
            if item.confidence > merged_map[item.path].confidence:
                merged_map[item.path] = item
        else:
            merged_map[item.path] = item
    return list(merged_map.values())
