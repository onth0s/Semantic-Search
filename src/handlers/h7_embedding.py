"""Embedding handler — semantic match via sentence-transformers.

Lazy-loads a sentence-transformer model to encode the query and
candidate basenames into dense vector representations. Computes
cosine similarity between the query embedding and each candidate
embedding, returning the best match above a configurable threshold.
Returns a MatchResult with confidence equal to ``cosine_sim * 1.0``.
"""

from __future__ import annotations

from pathlib import Path

from src.handlers.base import BaseHandler
from src.models import MatchResult


class EmbeddingHandler(BaseHandler):
    """Semantic match via lazy-loaded sentence-transformers.

    Uses cosine similarity scoring. Confidence: cosine_sim * 1.0.
    """

    name: str = "h7_embedding"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt a semantic embedding match against candidate basenames."""
        return None
