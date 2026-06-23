"""Heuristic Intent Detector for sempath.

Parses temporal, file type, and ordering keywords from queries to produce
canonical filter parameters and a cleaned search string.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta

import jellyfish
from rapidfuzz import fuzz

# Regexes
TEMPORAL_RE = re.compile(
    r"\b(?:modified|changed)?\s*(yesterday|today|last\s+week|last\s+month)\b",
    re.IGNORECASE,
)
LATEST_RE = re.compile(
    r"\b(latest|newest)\b",
    re.IGNORECASE,
)
LARGEST_RE = re.compile(
    r"\b(largest|biggest)\b",
    re.IGNORECASE,
)
DIR_INTENT_RE = re.compile(
    r"\b(dir|directory|folder|folders)\b",
    re.IGNORECASE,
)
FILE_INTENT_RE = re.compile(
    r"\b(file|files)\b",
    re.IGNORECASE,
)


def translate_wildcards(query: str) -> str:
    """Translate glob/wildcard patterns into descriptive English phrases for semantic search."""
    if not ("*" in query or "?" in query):
        return query

    # Normalize separators
    normalized = query.replace("\\", "/")
    parts = normalized.split("/")

    translated_parts = []
    for part in parts:
        if not ("*" in part or "?" in part):
            translated_parts.append(f"'{part}'")
            continue

        # Handle specific common wildcard patterns
        # 1. *.ext* (e.g. *.blend*) -> "a file whose name ends with .ext followed by any characters"
        if part.startswith("*.") and part.endswith("*") and len(part) > 3:
            ext = part[2:-1]
            desc = f"a file whose name ends with .{ext} followed by any characters"
        # 2. *.ext -> "a file ending in .ext"
        elif part.startswith("*.") and len(part) > 2:
            ext = part[2:]
            desc = f"a file ending in .{ext}"
        # 3. *name* -> "a file whose name contains name"
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            name = part[1:-1]
            desc = f"a file whose name contains '{name}'"
        # 4. *name -> "a file ending with name"
        elif part.startswith("*") and len(part) > 1:
            name = part[1:]
            desc = f"a file ending with '{name}'"
        # 5. name* -> "a file starting with name"
        elif part.endswith("*") and len(part) > 1:
            name = part[:-1]
            desc = f"a file starting with '{name}'"
        else:
            # General fallback: replace * with "any characters" and ? with "any single character"
            cleaned = part.replace("*", " any characters ").replace("?", " any single character ")
            cleaned = " ".join(cleaned.split())
            desc = f"a file matching '{cleaned}'"

        translated_parts.append(desc)

    if len(translated_parts) == 1:
        translated = translated_parts[0]
    else:
        # e.g., "a directory named 'dir' containing a file ending in .txt"
        result = ""
        for i, tp in enumerate(translated_parts):
            if i == 0:
                result = tp
            else:
                if tp.startswith("'"):
                    result = f"{result} containing a directory or file named {tp}"
                else:
                    result = f"{result} containing {tp}"
        translated = result

    # Log translation details
    from sempath.utils.logging import verbose_log

    verbose_log(
        f"[dim]Wildcard translation: '[bold cyan]{query}[/]' -> '[bold yellow]{translated}[/]'[/]"
    )

    return translated


@dataclass
class HeuristicsResult:
    clean_query: str
    extensions: list[str] | None = None
    age_limit: int | None = None
    directory_only: bool = False
    file_only: bool = False
    latest: bool = False
    largest: bool = False
    matched_categories: list[str] = field(default_factory=list)
    matched_category_keywords: dict[str, list[str]] = field(default_factory=dict)


def extract_heuristics(query: str, config: dict | None = None) -> HeuristicsResult:
    """Extract temporal, type, ordering, size, and directory/file intents from query.

    Returns:
        A dictionary with keys:
            - 'clean_query': query with heuristic terms removed and stripped.
            - 'modified_within_seconds': max age in seconds, or None.
            - 'extensions': list of lowercase extensions, or None.
            - 'latest': boolean indicating if 'latest'/'newest' was requested.
            - 'largest': boolean indicating if 'largest'/'biggest' was requested.
            - 'directory_only': boolean indicating if query is looking for a directory.
            - 'file_only': boolean indicating if query is looking for a file.
            - 'matched_categories': list of matched categories.
            - 'matched_category_keywords': dict of matched category keywords.
    """
    clean_query = query
    modified_within_seconds = None
    extensions = None
    latest = False
    largest = False
    directory_only = False
    file_only = False

    # Load categories config
    if config is None:
        from sempath.config import load_config

        try:
            config = load_config()
        except Exception:
            config = {}

    from sempath.config import DEFAULT_CONFIG

    default_categories = DEFAULT_CONFIG.get("heuristics", {}).get("categories", {})
    categories = config.get("heuristics", {}).get("categories", default_categories)
    category_fuzzy_threshold = config.get("heuristics", {}).get("category_fuzzy_threshold")
    if category_fuzzy_threshold is None:
        # Default to 80 to prevent false matches (e.g. song -> json at 75)
        category_fuzzy_threshold = 80

    from sempath.utils.logging import verbose_log

    # Temporal match
    temp_match = TEMPORAL_RE.search(clean_query)
    if temp_match:
        term = temp_match.group(1).lower()
        if term in ("yesterday", "today"):
            modified_within_seconds = int(timedelta(days=1).total_seconds())
        elif term == "last week":
            modified_within_seconds = int(timedelta(days=7).total_seconds())
        elif term == "last month":
            modified_within_seconds = int(timedelta(days=30).total_seconds())

        clean_query = TEMPORAL_RE.sub("", clean_query)

    # Latest match
    latest_match = LATEST_RE.search(clean_query)
    if latest_match:
        latest = True
        clean_query = LATEST_RE.sub("", clean_query)

    # Largest match
    largest_match = LARGEST_RE.search(clean_query)
    if largest_match:
        largest = True
        clean_query = LARGEST_RE.sub("", clean_query)

    # Directory intent match
    dir_match = DIR_INTENT_RE.search(clean_query)
    if dir_match:
        directory_only = True
        clean_query = DIR_INTENT_RE.sub("", clean_query)

    # File intent match
    file_match = FILE_INTENT_RE.search(clean_query)
    if file_match:
        file_only = True
        clean_query = FILE_INTENT_RE.sub("", clean_query)

    # Clean up whitespace runs
    clean_query = re.sub(r"\s+", " ", clean_query).strip()

    # Stopword stripping for heuristic search
    stopwords_set = {
        "of",
        "the",
        "a",
        "an",
        "in",
        "on",
        "at",
        "for",
        "with",
        "about",
        "to",
        "by",
        "from",
    }
    stopwords_re = re.compile(rf"\b({'|'.join(stopwords_set)})\b", re.IGNORECASE)
    clean_query = stopwords_re.sub(" ", clean_query)
    clean_query = re.sub(r"\s+", " ", clean_query).strip()

    # Category matching

    # Sort keywords by length in descending order
    keyword_pairs = []
    for cat_name, cat_info in categories.items():
        keywords = cat_info.get("keywords", [])
        for kw in keywords:
            keyword_pairs.append((kw, cat_name))

    keyword_pairs.sort(key=lambda x: len(x[0]), reverse=True)

    matched_categories = set()
    matched_category_keywords = {}

    # 1. Exact token matching
    for kw, cat_name in keyword_pairs:
        pattern = re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
        if pattern.search(clean_query):
            matched_categories.add(cat_name)
            matched_category_keywords.setdefault(cat_name, []).append(kw.lower())
            clean_query = pattern.sub(" ", clean_query)
            verbose_log(
                f"[dim]Exact category match: [bold cyan]{kw}[/] "
                f"in query matches category [bold green]{cat_name}[/].[/]"
            )

    # 2. Fuzzy and phonetic matching on remaining tokens
    tokens_to_check = re.findall(r"\b[a-zA-Z0-9_-]+\b", clean_query)
    for token in tokens_to_check:
        if len(token) < 3:
            continue

        for kw, cat_name in keyword_pairs:
            # Skip multi-word/compound keywords for fuzzy/phonetic
            if " " in kw or "-" in kw or "_" in kw:
                continue

            # Exact match check
            if token.lower() == kw.lower():
                matched_categories.add(cat_name)
                matched_category_keywords.setdefault(cat_name, []).append(token.lower())
                pattern = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
                clean_query = pattern.sub(" ", clean_query)
                verbose_log(
                    f"[dim]Exact category match (token): [bold cyan]{token}[/] "
                    f"matches keyword [bold cyan]{kw}[/] in category "
                    f"[bold green]{cat_name}[/].[/]"
                )
                break

            # Fuzzy check (only if keyword >= 4 chars and token >= 4 chars, unless threshold < 70)
            if category_fuzzy_threshold < 70 or (len(kw) >= 4 and len(token) >= 4):
                r = fuzz.ratio(token.lower(), kw.lower())
                if r >= category_fuzzy_threshold:
                    matched_categories.add(cat_name)
                    matched_category_keywords.setdefault(cat_name, []).append(token.lower())
                    pattern = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
                    clean_query = pattern.sub(" ", clean_query)
                    verbose_log(
                        f"[dim]Fuzzy category match: token [bold cyan]{token}[/] "
                        f"matches keyword [bold cyan]{kw}[/] (ratio: {r:.1f} >= "
                        f"{category_fuzzy_threshold}) in category [bold green]{cat_name}[/].[/]"
                    )
                    break

            # Phonetic check (only if keyword >= 4 chars, token >= 4 chars, and both alphabetic)
            if len(kw) >= 4 and len(token) >= 4 and token.isalpha() and kw.isalpha():
                try:
                    code_token = jellyfish.metaphone(token)
                    code_kw = jellyfish.metaphone(kw)
                    if (
                        code_token
                        and code_kw
                        and code_token == code_kw
                        and fuzz.ratio(token.lower(), kw.lower()) >= 50
                    ):
                        matched_categories.add(cat_name)
                        matched_category_keywords.setdefault(cat_name, []).append(token.lower())
                        pattern = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
                        clean_query = pattern.sub(" ", clean_query)
                        verbose_log(
                            f"[dim]Phonetic category match: token [bold cyan]{token}[/] "
                            f"matches keyword [bold cyan]{kw}[/] phonetically "
                            f"(Metaphone: {code_token}) in category "
                            f"[bold green]{cat_name}[/].[/]"
                        )
                        break
                except Exception:
                    pass

    # Collect extensions
    if matched_categories:
        extensions = []
        for cat_name in matched_categories:
            exts = categories[cat_name].get("extensions", [])
            for ext in exts:
                if ext not in extensions:
                    extensions.append(ext)
        extensions = sorted(extensions)

    # Clean up whitespace runs again
    clean_query = re.sub(r"\s+", " ", clean_query).strip()

    return HeuristicsResult(
        clean_query=clean_query,
        extensions=extensions,
        age_limit=modified_within_seconds,
        directory_only=directory_only,
        file_only=file_only,
        latest=latest,
        largest=largest,
        matched_categories=list(matched_categories),
        matched_category_keywords=matched_category_keywords,
    )
