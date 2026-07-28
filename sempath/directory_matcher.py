"""Directory content matching logic.

Provides functionality for resolving queries that target files inside a specific
directory based on heuristics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sempath.chain import build_chain
from sempath.constants import DIR_FUZZY_THRESHOLD
from sempath.utils.tokenize import normalize_tokens_with_wildcards


def _match_dir_name(clean_query: str, dir_name: str, config: dict[str, Any] | None) -> bool:
    """Check if query tokens match a directory name using fast handlers H1-H6."""
    q_tokens = normalize_tokens_with_wildcards(clean_query)
    p_tokens = normalize_tokens_with_wildcards(dir_name)
    if not q_tokens or not p_tokens:
        return False

    cfg = config or {}
    enabled_fast = [
        h
        for h in cfg.get("handlers", {}).get("enabled", ["h1", "h2", "h3", "h4", "h5", "h6"])
        if h in ("h1", "h2", "h3", "h4", "h5", "h6")
    ]
    if not enabled_fast:
        enabled_fast = ["h1", "h2", "h3", "h4", "h5", "h6"]

    fast_config = dict(cfg)
    fast_config["handlers"] = dict(cfg.get("handlers", {}))
    fast_config["handlers"]["enabled"] = enabled_fast
    fast_config["handlers"]["h4_threshold"] = DIR_FUZZY_THRESHOLD

    try:
        chain = build_chain(fast_config)
    except ValueError:
        return False

    synthetic_candidates = [Path(tok) for tok in p_tokens]

    for q_tok in q_tokens:
        matches = chain.handle(q_tok, synthetic_candidates)
        if not any(m.confidence >= 0.5 for m in matches):
            return False

    return True


def match_directory_content(
    clean_query: str,
    search_root: Path,
    candidates: list[Path],
    filtered_candidates: list[Path],
    config: dict[str, Any],
) -> tuple[Path | None, list[Path]]:
    """Find files inside a directory that matches the clean_query.

    Returns:
        A tuple of (matched_dir, descendants), where descendants are sorted.
    """
    if not clean_query:
        return None, []

    matching_dirs = []

    # 1. Check ancestors of search_root (including search_root itself)
    current = search_root.resolve()
    while True:
        if _match_dir_name(clean_query, current.name, config):
            matching_dirs.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent

    # 2. Check candidate directories under search_root
    for p in candidates:
        if p.is_dir() and _match_dir_name(clean_query, p.name, config):
            matching_dirs.append(p)

    if not matching_dirs:
        return None, []

    # Sort matching directories by path depth (shallowest first)
    matching_dirs.sort(key=lambda d: len(d.parts))

    descendants = []
    matched_dir = None
    for d in matching_dirs:
        # First try filtered_candidates
        for fc in filtered_candidates:
            if fc.is_file():
                try:
                    fc.relative_to(d)
                    descendants.append(fc)
                except ValueError:
                    pass
        # Fallback to candidates if filtered_candidates yielded no files for this directory
        if not descendants:
            for c in candidates:
                if c.is_file():
                    try:
                        c.relative_to(d)
                        descendants.append(c)
                    except ValueError:
                        pass
        if descendants:
            matched_dir = d
            break  # Use the first directory that has matching files

    if descendants:
        descendants.sort(key=lambda p: (len(p.parts), p.name.lower()))

    return matched_dir, descendants
