"""Lightweight in-memory stat cache to avoid redundant filesystem stat calls."""

from __future__ import annotations

import os
from pathlib import Path


class FileStatCache:
    """Caches os.stat and Path.stat results during a query lifecycle."""

    def __init__(self) -> None:
        self._cache: dict[Path, os.stat_result | None] = {}

    def get_stat(self, path: Path) -> os.stat_result | None:
        """Return cached stat result for path or query disk and store."""
        if path not in self._cache:
            try:
                self._cache[path] = path.stat()
            except (OSError, PermissionError):
                self._cache[path] = None
        return self._cache[path]

    def get_mtime(self, path: Path) -> float:
        """Return cached modification time, defaulting to 0.0 on error."""
        st = self.get_stat(path)
        return st.st_mtime if st is not None else 0.0

    def get_size(self, path: Path) -> int:
        """Return cached file size, returning 0 if directory or on error."""
        st = self.get_stat(path)
        if st is not None and not path.is_dir():
            return st.st_size
        return 0

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
