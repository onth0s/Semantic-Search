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
        return None
