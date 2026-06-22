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
        if not query or not candidates:
            return None

        from src.utils.tokenize import normalize_tokens

        query_tokens = normalize_tokens(query)
        if not query_tokens:
            return None

        # Split query by path separators to see how many parts we should check
        query_parts = [p for p in query.replace("\\", "/").split("/") if p]
        k = len(query_parts)

        matches = []
        for p in candidates:
            # 1. Base tokens matching name or stem
            if normalize_tokens(p.name) == query_tokens:
                matches.append(p)
                continue
            if normalize_tokens(p.stem) == query_tokens:
                matches.append(p)
                continue

            # 2. Path suffix tokens matching (for multi-part queries)
            if k > 1 and len(p.parts) >= k:
                suffix_parts = p.parts[-k:]
                suffix_str = "/".join(suffix_parts)
                if normalize_tokens(suffix_str) == query_tokens:
                    matches.append(p)

        if not matches:
            return None

        # Tie-breaker: shortest path depth first
        best = min(matches, key=lambda p: len(p.parts))
        return MatchResult(best, 0.9, self.name)
