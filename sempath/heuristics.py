"""Heuristic Intent Detector for sempath.

Parses temporal, file type, and ordering keywords from queries to produce
canonical filter parameters and a cleaned search string.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sempath.heuristics_parser import (
    STOPWORDS_RE,
    CategoryParser,
    OrderingAndIntentParser,
    TemporalParser,
    normalize_whitespace,
)


def translate_wildcards(query: str) -> str:
    """Translate glob/wildcard patterns into descriptive English phrases for semantic search."""
    if not ("*" in query or "?" in query):
        return query

    # Normalize separators
    from sempath.utils.tokenize import normalize_path_separators

    normalized = normalize_path_separators(query)
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
    name_query: str | None = None
    extensions: list[str] | None = None
    age_limit: int | None = None
    directory_only: bool = False
    file_only: bool = False
    latest: bool = False
    largest: bool = False
    smallest: bool = False
    oldest: bool = False
    matched_categories: list[str] = field(default_factory=list)
    matched_category_keywords: dict[str, list[str]] = field(default_factory=dict)


def _extract_temporal(query: str) -> tuple[str, int | None]:
    return TemporalParser.parse(query)


def _extract_sorting_and_intent(
    query: str,
) -> tuple[str, bool, bool, bool, bool, bool, bool]:
    return OrderingAndIntentParser.parse(query)


def _extract_categories(
    query: str, categories: dict, category_fuzzy_threshold: int
) -> tuple[str, list[str], dict[str, list[str]]]:
    return CategoryParser.extract_categories(query, categories, category_fuzzy_threshold)


def _normalize_whitespace(s: str) -> str:
    return normalize_whitespace(s)


def _match_extension_in_query(
    query: str, categories: dict
) -> tuple[str, list[str] | None, dict[str, list[str]] | None, list[str] | None]:
    return CategoryParser.match_extension_in_query(query, categories)


def extract_heuristics(query: str, config: dict | None = None) -> HeuristicsResult:
    """Extract temporal, type, ordering, size, and directory/file intents from query."""
    if config is None:
        from sempath.config import load_config

        try:
            config = load_config()
        except (OSError, Exception):
            config = {}

    from sempath.config import DEFAULT_CONFIG

    default_categories = DEFAULT_CONFIG.get("heuristics", {}).get("categories", {})
    categories = config.get("heuristics", {}).get("categories", default_categories)
    category_fuzzy_threshold = config.get("heuristics", {}).get("category_fuzzy_threshold", 80)

    # 1. Extract temporal parameters
    clean_query, modified_within_seconds = TemporalParser.parse(query)

    # Replace dashes and underscores with spaces (treat as word separators)
    clean_query = clean_query.replace("-", " ").replace("_", " ")

    # 2. Extract sorting and intent parameters
    (
        clean_query,
        latest,
        largest,
        smallest,
        oldest,
        directory_only,
        file_only,
    ) = OrderingAndIntentParser.parse(clean_query)

    # Clean up whitespace runs
    clean_query = normalize_whitespace(clean_query)

    # 3. Strip stopwords
    clean_query = STOPWORDS_RE.sub(" ", clean_query)
    clean_query = normalize_whitespace(clean_query)

    # Singularize remaining tokens for name matching
    from sempath.utils.tokenize import singularize_token

    name_query = " ".join(singularize_token(t) for t in clean_query.split())

    # 4. Extract categories — extension match has priority over keyword matching
    clean_query, ext_cats, ext_kws, explicit_exts = CategoryParser.match_extension_in_query(
        clean_query, categories
    )
    if ext_cats:
        matched_categories = ext_cats
        matched_category_keywords = ext_kws or {}
    else:
        clean_query, matched_categories, matched_category_keywords = (
            CategoryParser.extract_categories(clean_query, categories, category_fuzzy_threshold)
        )

    # Collect extensions
    extensions = None
    if explicit_exts:
        extensions = explicit_exts
    elif matched_categories:
        extensions = []
        for cat_name in matched_categories:
            exts = categories[cat_name].get("extensions", [])
            for ext in exts:
                if ext not in extensions:
                    extensions.append(ext)

    # When both directory_only and file category extensions co-occur
    # (e.g. "guns n roses dir songs"), prioritize category extension searching
    # over strict directory filtering to avoid zero candidates.
    if directory_only and extensions:
        directory_only = False
        file_only = True
        extensions = sorted(extensions)

    # Clean up whitespace runs again
    clean_query = normalize_whitespace(clean_query)

    # Singularize remaining tokens for semantic matching
    clean_query = " ".join(singularize_token(t) for t in clean_query.split())

    return HeuristicsResult(
        clean_query=clean_query,
        name_query=name_query,
        extensions=extensions,
        age_limit=modified_within_seconds,
        directory_only=directory_only,
        file_only=file_only,
        latest=latest,
        largest=largest,
        smallest=smallest,
        oldest=oldest,
        matched_categories=matched_categories,
        matched_category_keywords=matched_category_keywords,
    )
