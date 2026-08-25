"""Fuzzy match handler — edit-distance-based similarity.

Uses Levenshtein / Damerau-Levenshtein ratio via the ``rapidfuzz``
library to score the similarity between the query and each candidate
basename. A configurable threshold (default from config) determines
the minimum ratio required for a match. Returns a MatchResult with
confidence equal to ``ratio * 1.0``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rapidfuzz import fuzz

from sempath.handlers.base import BaseHandler
from sempath.models import MatchResult
from sempath.utils.tokenize import normalize_path_separators

if TYPE_CHECKING:
    from sempath.search_context import SearchContext


class FuzzyMatchHandler(BaseHandler):
    """Fuzzy string matching via rapidfuzz edit distance.

    Configurable threshold. Confidence: ratio * 1.0.
    """

    name: str = "h4_fuzzy"

    def match(
        self,
        query: str,
        candidates: list[Path],
        context: SearchContext | None = None,
    ) -> MatchResult | None:
        """Attempt a fuzzy match against candidate basenames."""
        matches = self.match_all(query, candidates, context=context)
        if not matches:
            return None

        # Select the highest ratio; break ties with shortest path depth
        return min(matches, key=lambda m: (-m.confidence, len(m.path.parts)))

    def match_all(
        self,
        query: str,
        candidates: list[Path],
        context: SearchContext | None = None,
    ) -> list[MatchResult]:
        """Attempt a fuzzy match against all candidates, returning all matches above threshold."""
        if not query or not candidates:
            return []

        threshold = self.config.get("handlers", {}).get("h4_threshold", 75)

        query_clean = query.replace("*", "").replace("?", "")
        if not query_clean:
            return []

        query_lower = query_clean.lower()
        query_pure = normalize_path_separators(query_lower)
        query_parts = [p for p in query_pure.split("/") if p]
        k = len(query_parts)

        results = []

        for p in candidates:
            p_name_lower = p.name.lower()
            p_stem_lower = p.stem.lower()

            r_name = fuzz.ratio(query_lower, p_name_lower)
            r_stem = fuzz.ratio(query_lower, p_stem_lower)
            r_token_set = fuzz.token_set_ratio(query_lower, p_stem_lower)
            r_max = max(r_name, r_stem, r_token_set)

            # Check partial ratio for queries with 4 or more chars and compatible length
            stem_len = len(p_stem_lower)
            q_len = len(query_clean)
            if q_len >= 4 and stem_len > 0:
                len_ratio = min(q_len, stem_len) / max(q_len, stem_len)
                if len_ratio >= 0.5:
                    r_partial = fuzz.partial_ratio(query_lower, p_stem_lower)
                    r_max = max(r_max, r_partial)

            if k > 1 and len(p.parts) >= k:
                suffix_parts = p.parts[-k:]
                suffix_str = "/".join(suffix_parts).lower()
                r_suffix = fuzz.ratio(query_pure, suffix_str)
                r_suffix_token = fuzz.token_set_ratio(query_pure, suffix_str)
                r_max = max(r_max, r_suffix, r_suffix_token)
                suffix_len = len(suffix_str)
                if q_len >= 4 and suffix_len > 0:
                    s_len_ratio = min(q_len, suffix_len) / max(q_len, suffix_len)
                    if s_len_ratio >= 0.5:
                        r_suffix_partial = fuzz.partial_ratio(query_pure, suffix_str)
                        r_max = max(r_max, r_suffix_partial)

            if r_max >= threshold:
                # Cap fuzzy match confidence at 0.80 maximum so fuzzy matches
                # never outrank exact (0.95), prefix (0.92), or sub-path token matches
                confidence = min(0.80, (r_max / 100.0) * 0.80)
                results.append(MatchResult(p, confidence, self.name))

        return results
