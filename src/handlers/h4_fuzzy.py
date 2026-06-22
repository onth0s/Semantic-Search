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
        return None
