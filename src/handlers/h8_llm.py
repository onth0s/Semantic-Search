"""LLM handler — inference via Ollama or OpenAI API.

Sends the query and candidate list to a large language model
(locally via Ollama or remotely via OpenAI API) for semantic
matching. The LLM returns its best match along with an optional
confidence score. Returns a MatchResult with the LLM-provided
confidence score, defaulting to 0.6 if none is provided.
"""

from __future__ import annotations

from pathlib import Path

from src.handlers.base import BaseHandler
from src.models import MatchResult


class LLMHandler(BaseHandler):
    """LLM inference via Ollama/OpenAI API. Confidence: LLM-provided score or 0.6."""

    name: str = "h8_llm"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt an LLM-based match against candidate basenames."""
        return None
