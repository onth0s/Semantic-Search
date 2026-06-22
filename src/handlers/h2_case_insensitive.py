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
        matches = []

        for p in candidates:
            p_name_lower = p.name.lower()
            p_stem_lower = p.stem.lower()

            # 1. Case-insensitive name match
            if p_name_lower == query_lower or p_stem_lower == query_lower:
                matches.append(p)
            # 3. Path suffix match (if query contains path separators)
            elif "/" in query_pure:
                p_str_lower = str(p).replace("\\", "/").lower()
                if p_str_lower.endswith(query_pure):
                    matches.append(p)

        if not matches:
            return None

        # Tie-breaker: shortest path depth first
        best = min(matches, key=lambda p: len(p.parts))
        return MatchResult(best, 0.95, self.name)
