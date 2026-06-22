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
        return None
