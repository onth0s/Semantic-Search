"""SearchContext carries query-specific context down the handler chain.

Eliminates mutable side-channels on the configuration dictionary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sempath.utils.stat_cache import FileStatCache


@dataclass
class SearchContext:
    """Context containing parameters and memoized state for the current search session."""

    raw_query: str
    search_root: Path
    top_n: int = 1
    non_interactive: bool = False
    config: dict[str, Any] = field(default_factory=dict)
    stat_cache: FileStatCache = field(default_factory=FileStatCache)
    metadata_cache: dict[Path, tuple[float, int, bool]] = field(default_factory=dict)

    def get_path_stat(self, path: Path) -> tuple[float, int, bool]:
        """Get (mtime, size, is_file) for a path with memoization in context."""
        if path not in self.metadata_cache:
            st = self.stat_cache.get_stat(path)
            if st is not None:
                try:
                    is_f = path.is_file()
                except (OSError, PermissionError):
                    is_f = False
                self.metadata_cache[path] = (st.st_mtime, st.st_size, is_f)
            else:
                self.metadata_cache[path] = (0.0, 0, False)
        return self.metadata_cache[path]
