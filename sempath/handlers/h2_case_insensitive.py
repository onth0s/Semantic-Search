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
        return matches[0]

    def match_all(
        self,
        query: str,
        candidates: list[Path],
        context: SearchContext | None = None,
    ) -> list[MatchResult]:
        """Attempt a case-insensitive, prefix, and substring match against candidate basenames."""
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
                    if p_stem_lower.startswith(query_lower) or p_name_lower.startswith(query_lower):
                        confidence = 0.92
                    elif query_lower in p_name_lower or query_lower in p_stem_lower:
                        confidence = 0.85
                    elif "/" in query_pure:
                        p_str_lower = normalize_path_separators(str(p)).lower()
                        if query_pure in p_str_lower:
                            confidence = 0.85

            if confidence > 0.0:
                results.append(MatchResult(p, confidence, self.name))

        if results:
            import re

            prefix = query_pure.split("*")[0].split("?")[0].lower() if is_glob else ""

            def _tie_breaker(m: MatchResult) -> tuple[float, int, int, int, int, str]:
                stem = m.path.stem.lower()
                is_copy = 1 if bool(re.search(r"\(\d+\)|\bcopy\b", stem)) else 0
                prefix_dist = 0 if prefix and stem.startswith(prefix) else (1 if prefix else 0)
                return (-m.confidence, prefix_dist, is_copy, len(m.path.parts), len(stem), stem)

            results.sort(key=_tie_breaker)

        return results
