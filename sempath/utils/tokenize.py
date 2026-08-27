"""Token splitting and normalisation utilities.

Used by the Token-Normalized handler (H3) and the Router to break
queries and candidate basenames into comparable token sets.
"""

from __future__ import annotations

import re

_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]+")
_LETTER_DIGIT_RE = re.compile(r"([a-zA-Z])(\d)")
_DIGIT_LETTER_RE = re.compile(r"(\d)([a-zA-Z])")


def singularize_token(token: str) -> str:
    """Normalize common English plural suffixes to singular for matching.

    Examples::
        >>> singularize_token("names")
        'name'
        >>> singularize_token("babies")
        'baby'
        >>> singularize_token("kisses")
        'kiss'
        >>> singularize_token("name")
        'name'
    """
    if token.endswith("sses"):
        return token[:-2]  # kisses -> kiss
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"  # babies -> baby
    if (
        token.endswith("s")
        and not token.endswith(("ss", "us", "is", "as", "ous"))
        and len(token) > 2
    ):
        return token[:-1]  # names -> name
    return token


def normalize_tokens(text: str) -> set[str]:
    """Normalise *text* into a set of lowercase alphanumeric tokens.

    Strips all non-alphanumeric characters, splits on letter-digit boundaries,
    whitespace and separator boundaries, and returns the unique token set.
    Plural suffixes are singularized.

    Examples::

        >>> normalize_tokens("Desktop/__MAIN")
        {'desktop', 'main'}
        >>> normalize_tokens("paper1")
        {'paper', '1'}
        >>> normalize_tokens("the main dir on dsktp")
        {'the', 'main', 'dir', 'on', 'dsktp'}
        >>> normalize_tokens("")
        set()
    """
    if not text:
        return set()

    # Split letter/digit boundaries
    spaced = _LETTER_DIGIT_RE.sub(r"\1 \2", text)
    spaced = _DIGIT_LETTER_RE.sub(r"\1 \2", spaced)

    # Replace non-alphanumeric runs with spaces, then split
    cleaned = _NON_ALNUM_RE.sub(" ", spaced).strip().lower()
    if not cleaned:
        return set()

    return {singularize_token(t) for t in cleaned.split()}


_WILD_RE = re.compile(r"[^a-zA-Z0-9*?]+")


def normalize_tokens_with_wildcards(text: str) -> set[str]:
    """Normalise text into a set of lowercase alphanumeric and wildcard tokens.

    Plural suffixes are singularized (wildcards are left intact).
    """
    if not text:
        return set()

    # Split letter/digit boundaries
    spaced = _LETTER_DIGIT_RE.sub(r"\1 \2", text)
    spaced = _DIGIT_LETTER_RE.sub(r"\1 \2", spaced)

    cleaned = _WILD_RE.sub(" ", spaced).strip().lower()
    if not cleaned:
        return set()
    return {singularize_token(t) if "*" not in t and "?" not in t else t for t in cleaned.split()}


def normalize_path_separators(path_str: str) -> str:
    """Normalize Windows-style backslashes to forward slashes for unified matching."""
    return path_str.replace("\\", "/")
