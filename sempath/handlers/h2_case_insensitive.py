"""Case-insensitive match handler — lower() comparison.

Converts both the query and each candidate basename to lowercase
before comparison. Catches trivial casing differences (e.g.
"MyProject" vs "myproject"). Returns a MatchResult with
confidence 0.95 on match.
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


class CaseInsensitiveHandler(BaseHandler):
    """lower() comparison of query to candidate basename. Confidence: 0.95."""

    name: str = "h2_case_insensitive"

    def match(
        self,
        query: str,
        candidates: list[Path],
        context: SearchContext | None = None,
    ) -> MatchResult | None:
        """Attempt a case-insensitive match against candidate basenames."""
        matches = self.match_all(query, candidates, context=context)
        if not matches:
            return None

        # Filter for the exact case-insensitive matches (confidence 0.95)
        # to preserve original behavior
        exact_matches = [m for m in matches if m.confidence >= 0.95]
        if not exact_matches:
            return None

        # Tie-breaker: shortest path depth first
        return min(exact_matches, key=lambda m: len(m.path.parts))

    def match_all(
        self,
        query: str,
        candidates: list[Path],
        context: SearchContext | None = None,
    ) -> list[MatchResult]:
        """Attempt a case-insensitive and substring match against candidate basenames."""
        if not query or not candidates:
            return []

        query_lower = query.lower()
        query_pure = normalize_path_separators(query_lower)
        is_glob = "*" in query or "?" in query
        results = []

        for p in candidates:
            p_name_lower = p.name.lower()
            p_stem_lower = p.stem.lower()
            p_suffixes = [s.lower() for s in path_suffixes(p, query)]

            confidence = 0.0

            if is_glob:
                if any(fnmatch.fnmatch(s, query_pure) for s in p_suffixes):
                    confidence = 0.95
            else:
                if p_name_lower == query_lower or p_stem_lower == query_lower:
                    confidence = 0.95
                elif "/" in query_pure:
                    p_str_lower = normalize_path_separators(str(p)).lower()
                    if p_str_lower.endswith(query_pure):
                        confidence = 0.95

                if confidence == 0.0:
                    if query_lower in p_name_lower or query_lower in p_stem_lower:
                        confidence = 0.85
                    elif "/" in query_pure:
                        p_str_lower = normalize_path_separators(str(p)).lower()
                        if query_pure in p_str_lower:
                            confidence = 0.85

            if confidence > 0.0:
                results.append(MatchResult(p, confidence, self.name))

        return results
