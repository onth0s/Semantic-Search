"""File operations and text inspection utilities for sempath."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sempath.constants import TEXT_FILE_MAX_BYTES


def is_text_file(path: Path) -> bool:
    """Return True if path points to a readable text file (non-binary and < 5MB)."""
    try:
        if not path.is_file():
            return False
        if path.stat().st_size > TEXT_FILE_MAX_BYTES:
            return False
        with open(path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return False
            try:
                chunk.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    chunk.decode("latin-1")
                except UnicodeDecodeError:
                    return False
        return True
    except (OSError, PermissionError):
        return False


def read_text_safely(path: Path) -> str | None:
    """Safely read text content of a file with utf-8 / latin-1 fallback."""
    if not is_text_file(path):
        return None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, PermissionError):
        return None


def extract_matching_snippets(
    content: str, query: str, max_snippets: int = 10
) -> list[tuple[int, str]]:
    """Extract line numbers and trimmed line texts matching query."""
    if not query or not content:
        return []
    snippets: list[tuple[int, str]] = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        if query in line:
            snippets.append((line_num, line.strip()))
            if len(snippets) >= max_snippets:
                break
    return snippets


def format_human_size(size_bytes: int | float) -> str:
    """Format bytes as human-readable string with exactly 2 decimal places."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def format_human_mtime(mtime: float) -> str:
    """Format a modification timestamp as a human-readable date-time string."""
    try:
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError):
        return "1970-01-01 00:00"


def get_path_file_meta(path: Path) -> str:
    """Return a compact '[size, date]' dimmed suffix for path."""
    try:
        st = path.stat()
        sz = format_human_size(st.st_size) if path.is_file() else "DIR"
        dt = format_human_mtime(st.st_mtime)
        return f" [dim][{sz}, {dt}][/]"
    except OSError:
        return ""
