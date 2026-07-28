"""Path suffix generation utilities for matching strategies."""

from __future__ import annotations

from pathlib import Path

from sempath.utils.tokenize import normalize_path_separators


def path_suffixes(p: Path, query: str) -> list[str]:
    """Generate candidate path suffixes for matching against a query.

    Returns basename, stem, and suffix slices (up to depth of query components)
    normalized with forward slashes.

    Args:
        p: Target filesystem path.
        query: Query string to match against.

    Returns:
        List of candidate path suffix strings to compare against the query.
    """
    normalized_q = normalize_path_separators(query)
    q_depth = len(normalized_q.split("/"))

    parts = list(p.parts)
    suffixes = [p.name, p.stem]

    # Include sliced path suffixes matching query depth
    for depth in range(2, min(q_depth + 2, len(parts) + 1)):
        suffix_str = "/".join(parts[-depth:])
        suffixes.append(suffix_str)

    return suffixes
