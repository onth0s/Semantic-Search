"""Case-insensitive match handler — lower() comparison.

Converts both the query and each candidate basename to lowercase
before comparison. Catches trivial casing differences (e.g.
"MyProject" vs "myproject"). Returns a MatchResult with
confidence 0.95 on match.
"""

from __future__ import annotations

from pathlib import Path

from src.handlers.base import BaseHandler
from src.models import MatchResult


class CaseInsensitiveHandler(BaseHandler):
    """lower() comparison of query to candidate basename. Confidence: 0.95."""

    name: str = "h2_case_insensitive"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt a case-insensitive match against candidate basenames."""
        if not query or not candidates:
            return None

        query_lower = query.lower()
        query_pure = query_lower.replace("\\", "/")
        is_glob = "*" in query or "?" in query
        matches = []

        import fnmatch

        for p in candidates:
            p_name_lower = p.name.lower()
            p_stem_lower = p.stem.lower()

            if is_glob:
                # 1. Case-insensitive glob name match
                if fnmatch.fnmatch(p_name_lower, query_lower) or fnmatch.fnmatch(
                    p_stem_lower, query_lower
                ):
                    matches.append(p)
                # 2. Case-insensitive glob path suffix match (if query contains path separators)
                elif "/" in query_pure:
                    query_parts = [part for part in query_pure.split("/") if part]
                    k = len(query_parts)
                    if len(p.parts) >= k:
                        p_suffix_lower = "/".join(part.lower() for part in p.parts[-k:])
                        if fnmatch.fnmatch(p_suffix_lower, query_pure):
                            matches.append(p)
            else:
                # 1. Case-insensitive name match
                if p_name_lower == query_lower or p_stem_lower == query_lower:
                    matches.append(p)
                # 2. Path suffix match (if query contains path separators)
                elif "/" in query_pure:
                    p_str_lower = str(p).replace("\\", "/").lower()
                    if p_str_lower.endswith(query_pure):
                        matches.append(p)

        if not matches:
            return None

        # Tie-breaker: shortest path depth first
        best = min(matches, key=lambda p: len(p.parts))
        return MatchResult(best, 0.95, self.name)

    def match_all(self, query: str, candidates: list[Path]) -> list[MatchResult]:
        """Attempt a case-insensitive and substring match against candidate basenames."""
        if not query or not candidates:
            return []

        query_lower = query.lower()
        query_pure = query_lower.replace("\\", "/")
        is_glob = "*" in query or "?" in query
        results = []

        import fnmatch

        for p in candidates:
            p_name_lower = p.name.lower()
            p_stem_lower = p.stem.lower()

            confidence = 0.0

            if is_glob:
                # 1. Case-insensitive glob name match
                if fnmatch.fnmatch(p_name_lower, query_lower) or fnmatch.fnmatch(
                    p_stem_lower, query_lower
                ):
                    confidence = 0.95
                # 2. Case-insensitive glob path suffix match (if query contains path separators)
                elif "/" in query_pure:
                    query_parts = [part for part in query_pure.split("/") if part]
                    k = len(query_parts)
                    if len(p.parts) >= k:
                        p_suffix_lower = "/".join(part.lower() for part in p.parts[-k:])
                        if fnmatch.fnmatch(p_suffix_lower, query_pure):
                            confidence = 0.95
            else:
                # 1. Case-insensitive name match
                if p_name_lower == query_lower or p_stem_lower == query_lower:
                    confidence = 0.95
                # 2. Path suffix match (if query contains path separators)
                elif "/" in query_pure:
                    p_str_lower = str(p).replace("\\", "/").lower()
                    if p_str_lower.endswith(query_pure):
                        confidence = 0.95

                # 3. Substring match fallback (non-wildcard only)
                if confidence == 0.0:
                    if query_lower in p_name_lower or query_lower in p_stem_lower:
                        confidence = 0.85
                    elif "/" in query_pure:
                        p_str_lower = str(p).replace("\\", "/").lower()
                        if query_pure in p_str_lower:
                            confidence = 0.85

            if confidence > 0.0:
                results.append(MatchResult(p, confidence, self.name))

        return results
