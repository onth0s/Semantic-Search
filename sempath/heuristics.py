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
    r"\b(latest|newest|lastest)\b",
    re.IGNORECASE,
)
OLDEST_RE = re.compile(
    r"\b(oldest)\b",
    re.IGNORECASE,
)
LARGEST_RE = re.compile(
    r"\b(largest|biggest)\b",
    re.IGNORECASE,
)
SMALLEST_RE = re.compile(
    r"\b(smallest|tiniest)\b",
    re.IGNORECASE,
)
DIR_INTENT_RE = re.compile(
    r"(?:^|\s)(dir|directory|folder|folders)(?:\s|$)",
    re.IGNORECASE,
)
FILE_INTENT_RE = re.compile(
    r"(?:^|\s)(file|files)(?:\s|$)",
    re.IGNORECASE,
)


STOPWORDS_SET = {
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
STOPWORDS_RE = re.compile(rf"\b({'|'.join(STOPWORDS_SET)})\b", re.IGNORECASE)


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
    """Extract temporal keyword intent from query."""
    clean_query = query
    modified_within_seconds = None
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
    return clean_query, modified_within_seconds


def _extract_sorting_and_intent(
    query: str,
) -> tuple[str, bool, bool, bool, bool, bool, bool]:
    """Extract latest, largest, smallest, oldest, directory_only, file_only intents."""
    clean_query = query
    latest = largest = smallest = oldest = False
    directory_only = file_only = False

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

    # Smallest match
    smallest_match = SMALLEST_RE.search(clean_query)
    if smallest_match:
        smallest = True
        clean_query = SMALLEST_RE.sub("", clean_query)

    # Oldest match
    oldest_match = OLDEST_RE.search(clean_query)
    if oldest_match:
        oldest = True
        clean_query = OLDEST_RE.sub("", clean_query)

    # Directory intent match
    dir_match = DIR_INTENT_RE.search(clean_query)
    if dir_match:
        directory_only = True
        clean_query = DIR_INTENT_RE.sub(" ", clean_query).strip()

    # File intent match
    file_match = FILE_INTENT_RE.search(clean_query)
    if file_match:
        file_only = True
        clean_query = FILE_INTENT_RE.sub(" ", clean_query).strip()

    return clean_query, latest, largest, smallest, oldest, directory_only, file_only


def _extract_categories(
    query: str, categories: dict, category_fuzzy_threshold: int
) -> tuple[str, list[str], dict[str, list[str]]]:
    """Extract keyword category matches and corresponding extensions from clean_query."""
    from sempath.utils.logging import verbose_log

    clean_query = query
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
        pattern = re.compile(rf"(?<!\.)\b{re.escape(kw)}\b(?!\.)", re.IGNORECASE)
        if pattern.search(clean_query):
            matched_categories.add(cat_name)
            matched_category_keywords.setdefault(cat_name, []).append(kw.lower())
            clean_query = pattern.sub(" ", clean_query)
            verbose_log(
                f"[dim]Exact category match: [bold cyan]{kw}[/] "
                f"in query matches category [bold green]{cat_name}[/].[/]"
            )

    # 2. Fuzzy and phonetic matching on remaining tokens
    tokens_to_check = re.findall(r"(?<!\.)\b[a-zA-Z0-9_-]+\b(?!\.)", clean_query)
    for token in tokens_to_check:
        if len(token) < 3:
            continue

        for kw, cat_name in keyword_pairs:
            if " " in kw or "-" in kw or "_" in kw:
                continue

            # Exact match check
            if token.lower() == kw.lower():
                matched_categories.add(cat_name)
                matched_category_keywords.setdefault(cat_name, []).append(token.lower())
                pattern = re.compile(rf"(?<!\.)\b{re.escape(token)}\b(?!\.)", re.IGNORECASE)
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
                    pattern = re.compile(rf"(?<!\.)\b{re.escape(token)}\b(?!\.)", re.IGNORECASE)
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
                        pattern = re.compile(rf"(?<!\.)\b{re.escape(token)}\b(?!\.)", re.IGNORECASE)
                        clean_query = pattern.sub(" ", clean_query)
                        verbose_log(
                            f"[dim]Phonetic category match: token [bold cyan]{token}[/] "
                            f"matches keyword [bold cyan]{kw}[/] phonetically "
                            f"(Metaphone: {code_token}) in category "
                            f"[bold green]{cat_name}[/].[/]"
                        )
                        break
                except (ValueError, TypeError):
                    pass

    return clean_query, list(matched_categories), matched_category_keywords


def _normalize_whitespace(s: str) -> str:
    """Normalize internal whitespace runs and strip leading/trailing spaces."""
    return re.sub(r"\s+", " ", s).strip()


def _match_extension_in_query(
    query: str, categories: dict
) -> tuple[str, list[str] | None, dict[str, list[str]] | None]:
    """Check if query ends with a recognized file extension.

    Returns (clean_query, matched_categories, matched_category_keywords) if found,
    or (query, None, None) so the caller can fall back to keyword matching.
    """
    import fnmatch

    from sempath.utils.logging import verbose_log

    ext_patterns: list[tuple[str, str]] = []
    for cat_name, cat_info in categories.items():
        for ext in cat_info.get("extensions", []):
            ext_patterns.append((ext, cat_name))

    if not ext_patterns:
        return query, None, None

    query_lower = query.lower().strip()
    last_dot = query_lower.rfind(".")
    if last_dot == -1 or last_dot == len(query_lower) - 1:
        return query, None, None

    suffix = query_lower[last_dot + 1 :]

    matched_categories: list[str] = []
    matched_keywords: dict[str, list[str]] = {}

    for ext, cat_name in ext_patterns:
        if fnmatch.fnmatch(suffix, ext.lower()):
            if cat_name not in matched_categories:
                matched_categories.append(cat_name)
            matched_keywords.setdefault(cat_name, []).append(suffix)
            verbose_log(
                f"[dim]Extension category match: query ends with "
                f"[bold cyan].{suffix}[/] → category [bold green]{cat_name}[/].[/]"
            )

    if matched_categories:
        # Strip extension suffix and dot from clean_query
        clean_query = query[:last_dot].strip()
        return clean_query, matched_categories, matched_keywords

    return query, None, None


def extract_heuristics(query: str, config: dict | None = None) -> HeuristicsResult:
    """Extract temporal, type, ordering, size, and directory/file intents from query."""
    # Load categories config
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
    clean_query, modified_within_seconds = _extract_temporal(query)

    # Replace dashes with spaces (treat as word separators)
    clean_query = clean_query.replace("-", " ")

    # 2. Extract sorting and intent parameters
    (
        clean_query,
        latest,
        largest,
        smallest,
        oldest,
        directory_only,
        file_only,
    ) = _extract_sorting_and_intent(clean_query)

    # Clean up whitespace runs
    clean_query = _normalize_whitespace(clean_query)

    # 3. Strip stopwords
    clean_query = STOPWORDS_RE.sub(" ", clean_query)
    clean_query = _normalize_whitespace(clean_query)

    # Singularize remaining tokens for name matching
    from sempath.utils.tokenize import singularize_token

    name_query = " ".join(singularize_token(t) for t in clean_query.split())

    # 4. Extract categories — extension match has priority over keyword matching
    clean_query, ext_cats, ext_kws = _match_extension_in_query(clean_query, categories)
    if ext_cats:
        matched_categories = ext_cats
        matched_category_keywords = ext_kws
    else:
        clean_query, matched_categories, matched_category_keywords = _extract_categories(
            clean_query, categories, category_fuzzy_threshold
        )

    # Collect extensions
    extensions = None
    if matched_categories:
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
    clean_query = _normalize_whitespace(clean_query)

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
