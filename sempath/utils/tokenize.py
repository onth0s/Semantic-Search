"""Token splitting and normalisation utilities.

Used by the Token-Normalized handler (H3) and the Router to break
queries and candidate basenames into comparable token sets.
"""

from __future__ import annotations

import re

_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]+")


def normalize_tokens(text: str) -> set[str]:
    """Normalise *text* into a set of lowercase alphanumeric tokens.

    Strips all non-alphanumeric characters, lowercases the result,
    splits on whitespace and separator boundaries, and returns the
    unique token set.

    Examples::

        >>> normalize_tokens("Desktop/__MAIN")
        {'desktop', 'main'}
        >>> normalize_tokens("the main dir on dsktp")
        {'the', 'main', 'dir', 'on', 'dsktp'}
        >>> normalize_tokens("")
        set()
    """
    if not text:
        return set()

    # Replace non-alphanumeric runs with spaces, then split
    cleaned = _NON_ALNUM_RE.sub(" ", text).strip().lower()
    if not cleaned:
        return set()

    return set(cleaned.split())


_WILD_RE = re.compile(r"[^a-zA-Z0-9*?]+")


def normalize_tokens_with_wildcards(text: str) -> set[str]:
    """Normalise text into a set of lowercase alphanumeric and wildcard tokens."""
    if not text:
        return set()

    cleaned = _WILD_RE.sub(" ", text).strip().lower()
    if not cleaned:
        return set()
    return set(cleaned.split())
