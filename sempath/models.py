"""Shared data models for sempath."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple


class MatchResult(NamedTuple):
    """A single match result from a handler.

    Attributes:
        path: The matched filesystem path.
        confidence: Confidence score between 0.0 and 1.0.
        handler: Name of the handler that produced this match.
    """

    path: Path
    confidence: float
    handler: str


@dataclass
class SearchResult:
    """Aggregated search result wrapping match status and details.

    Maps directly to the JSON output schemas defined in the CLI spec:
    - ``status="success"`` — a single confident match was found.
    - ``status="ambiguous"`` — no match above threshold, but near-misses exist.
    - ``status="failed"`` — no candidate paths or near-misses matched.

    Attributes:
        status: One of ``"success"``, ``"ambiguous"``, or ``"failed"``.
        query: The original search query string.
        match: The top match (only set when status is ``"success"``).
        near_misses: Ranked list of near-miss candidates.
        message: Human-readable status message.
    """

    status: str
    query: str
    match: MatchResult | None = None
    near_misses: list[MatchResult] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for JSON output.

        Path objects are converted to strings. Only populated fields
        are included in the output.
        """
        result: dict = {
            "status": self.status,
            "query": self.query,
        }

        if self.match is not None:
            result["match"] = {
                "path": str(self.match.path),
                "confidence": self.match.confidence,
                "handler": self.match.handler,
            }

        if self.message:
            result["message"] = self.message

        result["near_misses"] = [
            {
                "path": str(m.path),
                "confidence": m.confidence,
                "handler": m.handler,
            }
            for m in self.near_misses
        ]

        return result
