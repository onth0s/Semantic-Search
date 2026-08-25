"""Sub-parsers and domain-specific extraction components for sempath heuristics."""

from __future__ import annotations

import fnmatch
import re
from datetime import timedelta

import jellyfish
from rapidfuzz import fuzz

TEMPORAL_RE = re.compile(
    r"\b(?:modified|changed)?\s*(yesterday|today|last\s+week|last\s+month)\b",
    re.IGNORECASE,
)
LATEST_RE = re.compile(r"\b(latest|newest|lastest)\b", re.IGNORECASE)
OLDEST_RE = re.compile(r"\b(oldest)\b", re.IGNORECASE)
LARGEST_RE = re.compile(r"\b(largest|biggest)\b", re.IGNORECASE)
SMALLEST_RE = re.compile(r"\b(smallest|tiniest)\b", re.IGNORECASE)
DIR_INTENT_RE = re.compile(r"(?:^|\s)(dir|directory|folder|folders)(?:\s|$)", re.IGNORECASE)
FILE_INTENT_RE = re.compile(r"(?:^|\s)(file|files)(?:\s|$)", re.IGNORECASE)

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


def normalize_whitespace(s: str) -> str:
    """Normalize internal whitespace runs and strip leading/trailing spaces."""
    return re.sub(r"\s+", " ", s).strip()


class TemporalParser:
    """Extracts temporal parameters like today, yesterday, last week, last month."""

    @staticmethod
    def parse(query: str) -> tuple[str, int | None]:
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


class OrderingAndIntentParser:
    """Extracts sorting preferences (latest, largest, etc.) and file/dir intent."""

    @staticmethod
    def parse(query: str) -> tuple[str, bool, bool, bool, bool, bool, bool]:
        clean_query = query
        latest = largest = smallest = oldest = False
        directory_only = file_only = False

        latest_matches = list(LATEST_RE.finditer(clean_query))
        if latest_matches:
            latest = True
            last_m = latest_matches[-1]
            clean_query = clean_query[: last_m.start()] + clean_query[last_m.end() :]

        largest_matches = list(LARGEST_RE.finditer(clean_query))
        if largest_matches:
            largest = True
            last_m = largest_matches[-1]
            clean_query = clean_query[: last_m.start()] + clean_query[last_m.end() :]

        smallest_matches = list(SMALLEST_RE.finditer(clean_query))
        if smallest_matches:
            smallest = True
            last_m = smallest_matches[-1]
            clean_query = clean_query[: last_m.start()] + clean_query[last_m.end() :]

        oldest_matches = list(OLDEST_RE.finditer(clean_query))
        if oldest_matches:
            oldest = True
            last_m = oldest_matches[-1]
            clean_query = clean_query[: last_m.start()] + clean_query[last_m.end() :]

        dir_match = DIR_INTENT_RE.search(clean_query)
        if dir_match:
            directory_only = True
            clean_query = DIR_INTENT_RE.sub(" ", clean_query).strip()

        file_match = FILE_INTENT_RE.search(clean_query)
        if file_match:
            file_only = True
            clean_query = FILE_INTENT_RE.sub(" ", clean_query).strip()

        return clean_query, latest, largest, smallest, oldest, directory_only, file_only


class CategoryParser:
    """Extracts keyword categories and explicit file extensions from queries."""

    @staticmethod
    def match_extension_in_query(
        query: str, categories: dict
    ) -> tuple[str, list[str] | None, dict[str, list[str]] | None, list[str] | None]:
        from sempath.utils.logging import verbose_log

        ext_patterns: list[tuple[str, str]] = []
        for cat_name, cat_info in categories.items():
            for ext in cat_info.get("extensions", []):
                ext_patterns.append((ext, cat_name))

        if not ext_patterns:
            return query, None, None, None

        query_lower = query.lower().strip()
        matched_categories: list[str] = []
        matched_keywords: dict[str, list[str]] = {}

        # 1. Check dot-separated suffix (e.g. "bee.exe")
        last_dot = query_lower.rfind(".")
        if last_dot != -1 and last_dot < len(query_lower) - 1:
            suffix = query_lower[last_dot + 1 :]
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
                clean_query = query[:last_dot].strip()
                return clean_query, matched_categories, matched_keywords, [suffix]

        # 2. Check whitespace-separated last token (e.g. "bee exe")
        tokens = query_lower.split()
        if len(tokens) > 1:
            last_token = tokens[-1]
            for ext, cat_name in ext_patterns:
                if fnmatch.fnmatch(last_token, ext.lower()):
                    if cat_name not in matched_categories:
                        matched_categories.append(cat_name)
                    matched_keywords.setdefault(cat_name, []).append(last_token)
                    verbose_log(
                        f"[dim]Extension category match: query ends with token "
                        f"[bold cyan]{last_token}[/] → category [bold green]{cat_name}[/].[/]"
                    )
            if matched_categories:
                last_token_idx = query_lower.rfind(last_token)
                clean_query = query[:last_token_idx].strip()
                return clean_query, matched_categories, matched_keywords, [last_token]

        return query, None, None, None

    @staticmethod
    def extract_categories(
        query: str, categories: dict, category_fuzzy_threshold: int
    ) -> tuple[str, list[str], dict[str, list[str]]]:
        from sempath.utils.logging import verbose_log

        clean_query = query
        keyword_pairs = []
        for cat_name, cat_info in categories.items():
            keywords = cat_info.get("keywords", [])
            for kw in keywords:
                keyword_pairs.append((kw, cat_name))

        keyword_pairs.sort(key=lambda x: len(x[0]), reverse=True)
        matched_categories = set()
        matched_category_keywords: dict[str, list[str]] = {}

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
                            pattern = re.compile(
                                rf"(?<!\.)\b{re.escape(token)}\b(?!\.)", re.IGNORECASE
                            )
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
