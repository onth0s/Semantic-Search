"""Phonetic match handler — sound-based encoding comparison.

Uses Metaphone encoding via the ``jellyfish`` library
to generate phonetic representations of the query and candidate
basenames. Catches homophones and phonetically similar names.
Returns a MatchResult with confidence 0.75 on match.
"""

from __future__ import annotations

from pathlib import Path

from src.handlers.base import BaseHandler
from src.models import MatchResult


class PhoneticMatchHandler(BaseHandler):
    """Soundex/Metaphone encoding via jellyfish. Catches homophones. Confidence: 0.75."""

    name: str = "h5_phonetic"

    def _get_phonetic_codes(self, text: str) -> set[str]:
        """Convert a string into a set of phonetic codes."""
        import jellyfish

        from src.utils.tokenize import normalize_tokens

        codes = set()
        for token in normalize_tokens(text):
            if token.isalpha():
                try:
                    code = jellyfish.metaphone(token)
                    if code:
                        codes.add(code)
                except Exception:
                    pass
            else:
                # Keep numeric/alphanumeric mixtures as-is for comparison
                codes.add(token)
        return codes

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt a phonetic match against candidate basenames."""
        if not query or not candidates:
            return None

        query_clean = query.replace("*", "").replace("?", "")
        if not query_clean:
            return None

        query_codes = self._get_phonetic_codes(query_clean)
        if not query_codes:
            return None

        # Split query by path separators to check subpath suffixes
        query_parts = [p for p in query_clean.replace("\\", "/").split("/") if p]
        k = len(query_parts)

        matches = []
        for p in candidates:
            # 1. Base phonetic code matching name or stem
            if self._get_phonetic_codes(p.name) == query_codes:
                matches.append(p)
                continue
            if self._get_phonetic_codes(p.stem) == query_codes:
                matches.append(p)
                continue

            # 2. Path suffix phonetic code matching (for multi-part queries)
            if k > 1 and len(p.parts) >= k:
                suffix_parts = p.parts[-k:]
                suffix_str = "/".join(suffix_parts)
                if self._get_phonetic_codes(suffix_str) == query_codes:
                    matches.append(p)

        if not matches:
            return None

        # Tie-breaker: shortest path depth first
        best = min(matches, key=lambda p: len(p.parts))
        return MatchResult(best, 0.75, self.name)

    def match_all(self, query: str, candidates: list[Path]) -> list[MatchResult]:
        """Attempt a phonetic match against candidate basenames, returning all matches."""
        if not query or not candidates:
            return []

        query_clean = query.replace("*", "").replace("?", "")
        if not query_clean:
            return []

        query_codes = self._get_phonetic_codes(query_clean)
        if not query_codes:
            return []

        # Split query by path separators to check subpath suffixes
        query_parts = [p for p in query_clean.replace("\\", "/").split("/") if p]
        k = len(query_parts)

        results = []
        for p in candidates:
            # 1. Base phonetic code matching name or stem
            if self._get_phonetic_codes(p.name) == query_codes or self._get_phonetic_codes(p.stem) == query_codes:
                results.append(MatchResult(p, 0.75, self.name))
                continue

            # 2. Path suffix phonetic code matching (for multi-part queries)
            if k > 1 and len(p.parts) >= k:
                suffix_parts = p.parts[-k:]
                suffix_str = "/".join(suffix_parts)
                if self._get_phonetic_codes(suffix_str) == query_codes:
                    results.append(MatchResult(p, 0.75, self.name))

        return results
