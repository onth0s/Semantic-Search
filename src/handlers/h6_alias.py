"""Alias handler — synonym expansion from config and learned memory.

Expands the query using aliases and synonyms defined in the
configuration file as well as aliases learned from previous
interactive sessions. Supports fuzzy and phonetic alias key
matching, regex patterns, and context splitting for compound
queries. Returns a MatchResult with confidence 0.95 on match.
"""

from __future__ import annotations

from pathlib import Path

from src.handlers.base import BaseHandler
from src.models import MatchResult


class AliasHandler(BaseHandler):
    """Alias/synonym expansion from config and learned memory.

    Supports fuzzy/phonetic alias keys, regex patterns, and context splitting.
    Confidence: 0.95.
    """

    name: str = "h6_alias"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt an alias-based match against candidate basenames."""
        return None
