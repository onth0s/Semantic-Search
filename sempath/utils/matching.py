"""Matching utilities for merging and manipulating MatchResult objects."""

from __future__ import annotations

from sempath.models import MatchResult


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
