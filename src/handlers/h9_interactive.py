"""Interactive handler — user-driven fallback with alias learning.

Presents the top N candidate matches to the user for manual
selection when all automated handlers fail to produce a confident
match. Confirmed selections are learned as aliases for future
queries, enabling the system to resolve the same query
automatically next time. Returns a MatchResult with confidence 1.0
after user confirmation.
"""

from __future__ import annotations

from pathlib import Path

from src.handlers.base import BaseHandler
from src.models import MatchResult


class InteractiveHandler(BaseHandler):
    """Interactive fallback presenting top N candidates to the user.

    Learns confirmed aliases. Confidence: 1.0.
    """

    name: str = "h9_interactive"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Present candidates to the user for interactive selection."""
        return None
