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
        snippets: List of matching line context tuples (line_number, line_text).
    """

    path: Path
    confidence: float
    handler: str
    snippets: tuple[tuple[int, str], ...] = ()


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
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for JSON output.

        Path objects are converted to strings. Only populated fields
        are included in the output.
        """
        result: dict = {
            "status": self.status,
            "query": self.query,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
        }

        def _format_match(m: MatchResult) -> dict:
            d: dict = {
                "path": str(m.path),
                "confidence": m.confidence,
                "handler": m.handler,
            }
            if m.snippets:
                d["snippets"] = [{"line": line_num, "text": text} for line_num, text in m.snippets]
            return d

        if self.match is not None:
            result["match"] = _format_match(self.match)

        if self.message:
            result["message"] = self.message

        result["near_misses"] = [_format_match(m) for m in self.near_misses]

        return result
