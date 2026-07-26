"""Directory content matching logic.

Provides functionality for resolving queries that target files inside a specific
directory based on heuristics.
"""

from __future__ import annotations

import contextlib
import fnmatch
from pathlib import Path
from typing import Any

import jellyfish
from rapidfuzz import fuzz


def _match_dir_name(q_tokens: list[str], dir_name: str, config: dict[str, Any] | None) -> bool:
    """Check if query tokens match a directory name (exact, fuzzy, phonetic, or alias)."""
    if not q_tokens or not dir_name:
        return False

    from sempath.utils.tokenize import normalize_tokens_with_wildcards

    p_tokens = normalize_tokens_with_wildcards(dir_name)
    if not p_tokens:
        return False

    aliases = config.get("aliases", {}) if config else {}
    token_to_aliases = {}
    for alias_key, alias_values in aliases.items():
        key_norm = alias_key.lower()
        val_norms = {v.lower() for v in alias_values}
        all_norms = val_norms.union({key_norm})
        for tok in all_norms:
            token_to_aliases.setdefault(tok, set()).add(key_norm)

    for q_tok in q_tokens:
        matched = False
        q_tok_lower = q_tok.lower()

        q_meta = None
        if q_tok_lower.isalpha():
            with contextlib.suppress(Exception):
                q_meta = jellyfish.metaphone(q_tok_lower)

        q_aliases = token_to_aliases.get(q_tok_lower, set())

        for p_tok in p_tokens:
            p_tok_lower = p_tok.lower()

            # 1. Exact match
            if q_tok_lower == p_tok_lower:
                matched = True
                break

            # 2. Wildcard/glob match
            if ("*" in q_tok_lower or "?" in q_tok_lower) and fnmatch.fnmatch(
                p_tok_lower, q_tok_lower
            ):
                matched = True
                break
            if ("*" in p_tok_lower or "?" in p_tok_lower) and fnmatch.fnmatch(
                q_tok_lower, p_tok_lower
            ):
                matched = True
                break

            # 3. Alias match
            p_aliases = token_to_aliases.get(p_tok_lower, set())
            if q_aliases and p_aliases and q_aliases.intersection(p_aliases):
                matched = True
                break

            # 4. Fuzzy match (requires length >= 4)
            if (
                len(q_tok_lower) >= 4
                and len(p_tok_lower) >= 4
                and (
                    q_tok_lower in p_tok_lower
                    or p_tok_lower in q_tok_lower
                    or fuzz.ratio(q_tok_lower, p_tok_lower) >= 80
                )
            ):
                matched = True
                break

            # 5. Phonetic match (requires length >= 4)
            if len(q_tok_lower) >= 4 and len(p_tok_lower) >= 4 and q_meta and p_tok_lower.isalpha():
                try:
                    p_meta = jellyfish.metaphone(p_tok_lower)
                    if q_meta == p_meta and fuzz.ratio(q_tok_lower, p_tok_lower) >= 50:
                        matched = True
                        break
                except Exception:
                    pass

        if not matched:
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
    from sempath.utils.tokenize import normalize_tokens_with_wildcards

    q_tokens = normalize_tokens_with_wildcards(clean_query)
    if not q_tokens:
        return None, []

    matching_dirs = []

    # 1. Check ancestors of search_root (including search_root itself)
    current = search_root.resolve()
    while True:
        if _match_dir_name(q_tokens, current.name, config):
            matching_dirs.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent

    # 2. Check candidate directories under search_root
    for p in candidates:
        if p.is_dir() and _match_dir_name(q_tokens, p.name, config):
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
