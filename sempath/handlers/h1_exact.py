"""Exact match handler — direct string comparison.

Compares the query string directly (==) against each candidate's
basename (stem). If an exact match is found, returns a MatchResult
with confidence 1.0. This is the fastest and most precise handler
in the chain, so it runs first.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

from sempath.handlers.base import BaseHandler
from sempath.models import MatchResult
from sempath.utils.path_suffixes import path_suffixes
from sempath.utils.tokenize import normalize_path_separators

if TYPE_CHECKING:
    from sempath.search_context import SearchContext


class ExactMatchHandler(BaseHandler):
    """Direct == comparison of query to candidate basename. Confidence: 1.0."""

    name: str = "h1_exact"

    def match(
        self,
        query: str,
        candidates: list[Path],
        context: SearchContext | None = None,
    ) -> MatchResult | None:
        """Attempt an exact string match against candidate basenames."""
        matches = self.match_all(query, candidates, context=context)
        if not matches:
            return None
        # Tie-breaker: shortest path depth first
        return min(matches, key=lambda m: len(m.path.parts))

    def match_all(
        self,
        query: str,
        candidates: list[Path],
        context: SearchContext | None = None,
    ) -> list[MatchResult]:
        """Attempt an exact string match against candidate basenames, returning all matches."""
        if not query or not candidates:
            return []

        query_pure = normalize_path_separators(query)
        is_glob = "*" in query or "?" in query
        matches = []

        for p in candidates:
            p_suffixes = path_suffixes(p, query)
            if is_glob:
                if any(fnmatch.fnmatchcase(s, query_pure) for s in p_suffixes):
                    matches.append(MatchResult(p, 1.0, self.name))
            else:
                p_str = normalize_path_separators(str(p))
                if (
                    p.name == query
                    or p.stem == query
                    or ("/" in query_pure and p_str.endswith(query_pure))
                ):
                    matches.append(MatchResult(p, 1.0, self.name))

        return matches
