"""Exact match handler — direct string comparison.

Compares the query string directly (==) against each candidate's
basename (stem). If an exact match is found, returns a MatchResult
with confidence 1.0. This is the fastest and most precise handler
in the chain, so it runs first.
"""

from __future__ import annotations

from pathlib import Path

from src.handlers.base import BaseHandler
from src.models import MatchResult


class ExactMatchHandler(BaseHandler):
    """Direct == comparison of query to candidate basename. Confidence: 1.0."""

    name: str = "h1_exact"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt an exact string match against candidate basenames."""
        if not query or not candidates:
            return None

        query_pure = query.replace("\\", "/")
        matches = []

        for p in candidates:
            # 1. Exact name match
            if p.name == query or p.stem == query:
                matches.append(p)
            # 3. Path suffix match (if query contains path separators)
            elif "/" in query_pure:
                p_str = str(p).replace("\\", "/")
                if p_str.endswith(query_pure):
                    matches.append(p)

        if not matches:
            return None

        # Tie-breaker: shortest path depth first
        best = min(matches, key=lambda p: len(p.parts))
        return MatchResult(best, 1.0, self.name)
