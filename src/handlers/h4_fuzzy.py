"""Fuzzy match handler — edit-distance-based similarity.

Uses Levenshtein / Damerau-Levenshtein ratio via the ``rapidfuzz``
library to score the similarity between the query and each candidate
basename. A configurable threshold (default from config) determines
the minimum ratio required for a match. Returns a MatchResult with
confidence equal to ``ratio * 1.0``.
"""

from __future__ import annotations

from pathlib import Path

from src.handlers.base import BaseHandler
from src.models import MatchResult


class FuzzyMatchHandler(BaseHandler):
    """Fuzzy string matching via rapidfuzz edit distance.

    Configurable threshold. Confidence: ratio * 1.0.
    """

    name: str = "h4_fuzzy"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt a fuzzy match against candidate basenames."""
        if not query or not candidates:
            return None

        from rapidfuzz import fuzz

        threshold = self.config.get("handlers", {}).get("h4_threshold", 75)

        query_clean = query.replace("*", "").replace("?", "")
        if not query_clean:
            return None

        query_lower = query_clean.lower()
        query_pure = query_lower.replace("\\", "/")
        query_parts = [p for p in query_pure.split("/") if p]
        k = len(query_parts)

        best_p = None
        best_ratio = -1.0

        for p in candidates:
            r_name = fuzz.ratio(query_lower, p.name.lower())
            r_stem = fuzz.ratio(query_lower, p.stem.lower())
            r_max = max(r_name, r_stem)

            if k > 1 and len(p.parts) >= k:
                suffix_parts = p.parts[-k:]
                suffix_str = "/".join(suffix_parts).lower()
                r_suffix = fuzz.ratio(query_pure, suffix_str)
                r_max = max(r_max, r_suffix)

            if r_max >= threshold:
                # Select the highest ratio; break ties with shortest path depth
                if r_max > best_ratio:
                    best_ratio = r_max
                    best_p = p
                elif r_max == best_ratio:
                    if len(p.parts) < len(best_p.parts):
                        best_p = p

        if best_p is None:
            return None

        return MatchResult(best_p, best_ratio / 100.0, self.name)
