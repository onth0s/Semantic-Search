"""Phonetic match handler — sound-based encoding comparison.

Uses Soundex and/or Metaphone encoding via the ``jellyfish`` library
to generate phonetic representations of the query and candidate
basenames. Catches homophones and phonetically similar names (e.g.
"colour" vs "color"). Returns a MatchResult with confidence 0.75
on match.
"""

from __future__ import annotations

from pathlib import Path

from src.handlers.base import BaseHandler
from src.models import MatchResult


class PhoneticMatchHandler(BaseHandler):
    """Soundex/Metaphone encoding via jellyfish. Catches homophones. Confidence: 0.75."""

    name: str = "h5_phonetic"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt a phonetic match against candidate basenames."""
        return None
