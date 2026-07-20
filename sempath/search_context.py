"""SearchContext carries query-specific context down the handler chain.

Eliminates the mutable side-channels on the configuration dictionary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SearchContext:
    """Read-only context containing parameters for the current search session."""

    raw_query: str
    search_root: Path
    top_n: int
    non_interactive: bool = False
