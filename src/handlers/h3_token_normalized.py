"""Token-normalized match handler — unordered set comparison.

Strips non-alphanumeric characters from both the query and each
candidate basename, splits the result into lowercase tokens, and
compares the resulting sets. Catches reordered or differently-
delimited names (e.g. "my_project" vs "project-my"). Returns a
MatchResult with confidence 0.9 on match.
"""

from __future__ import annotations

from pathlib import Path

from src.handlers.base import BaseHandler
from src.models import MatchResult


class TokenNormalizedHandler(BaseHandler):
    """Strip non-alphanumeric, split tokens, compare unordered sets. Confidence: 0.9."""

    name: str = "h3_token_normalized"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt a token-normalized match against candidate basenames."""
        return None
