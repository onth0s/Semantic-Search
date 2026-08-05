"""Formatting and presentation utilities for the sempath CLI."""

from __future__ import annotations

import re
from pathlib import Path

import click
from rich.markup import escape

from sempath.utils.console import console

_GENERIC_STEMS: frozenset[str] = frozenset(
    {
        "unnamed",
        "unname2d",
        "untitled",
        "temp",
        "tmp",
        "test",
        "var",
        "deleteme",
        "copy",
        "newfolder",
    }
)

_GROUP_OTHER = "Other matches"
_GROUP_GENERIC = "Generic/placeholder files"


def _is_generic_stem(stem: str) -> bool:
    """Return True if the stem is a placeholder/generic filename."""
    cleaned = re.sub(r"[\s\-_0-9()]+", "", stem.lower())
    return cleaned in _GENERIC_STEMS


def _format_elapsed_time(seconds: float) -> str:
    """Format elapsed time in seconds as human-readable string (e.g. 42ms, 0.15s)."""
    if seconds < 1.0:
        ms = seconds * 1000.0
        return f"{ms:.0f}ms" if ms >= 1.0 else f"{seconds * 1000.0:.1f}ms"
    return f"{seconds:.2f}s"


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable string with 2 decimal places."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def _human_mtime(mtime: float) -> str:
    """Format a modification timestamp as a human-readable date-time string."""
    from datetime import datetime

    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")


def _format_file_meta(path: Path) -> str:
    """Return a compact '[size, date]' dimmed suffix for *path*."""
    try:
        st = path.stat()
        sz = _human_size(st.st_size) if path.is_file() else "DIR"
        dt = _human_mtime(st.st_mtime)
        return f" [dim][{sz}, {dt}][/]"
    except OSError:
        return ""


def _format_snippet(snippet_text: str, query: str | None = None) -> str:
    """Format snippet text without dimming, highlighting exact case-sensitive query matches."""
    if not query or not query.strip() or query.strip() in (".", "*"):
        return escape(snippet_text)

    # Exact case-sensitive replacement of query matches with bold yellow/amber highlight
    pattern = re.compile(re.escape(query))
    parts = []
    last_idx = 0
    for match in pattern.finditer(snippet_text):
        parts.append(escape(snippet_text[last_idx : match.start()]))
        matched_str = escape(match.group(0))
        parts.append(f"[bold yellow]{matched_str}[/]")
        last_idx = match.end()
    parts.append(escape(snippet_text[last_idx:]))
    return "".join(parts)


def _classify_match(path: Path, search_root: Path) -> str:
    """Return the display group label for a near-miss match."""
    if _is_generic_stem(path.stem):
        return _GROUP_GENERIC

    # Determine if it has a subfolder parent relative to search_root
    try:
        rel_path = path.resolve().relative_to(search_root.resolve())
        if rel_path.parent == Path("."):
            return _GROUP_OTHER
        from sempath.utils.tokenize import normalize_path_separators

        return normalize_path_separators(str(rel_path.parent))
    except (ValueError, OSError):
        return _GROUP_OTHER


def _print_grouped_matches(
    matches: list,
    limit: int,
    verbose: bool,
    query: str | None = None,
    start_index: int = 1,
) -> int:
    """Print *matches* (up to *limit*) sorted into display groups with 1-indexed numbering.

    Returns the next available 1-based item index after printing.
    """
    from collections import defaultdict

    ctx = click.get_current_context(silent=True)
    search_root = ctx.obj.get("root", Path(".")) if (ctx and ctx.obj) else Path(".")

    # Bucket all matches first
    groups: dict[str, list] = defaultdict(list)
    for nm in matches:
        group_lbl = _classify_match(nm.path, search_root)
        groups[group_lbl].append(nm)

    all_groups = list(groups.keys())
    subfolder_groups = [g for g in all_groups if g not in (_GROUP_OTHER, _GROUP_GENERIC)]

    group_order = []
    if _GROUP_OTHER in groups:
        group_order.append(_GROUP_OTHER)
    group_order.extend(subfolder_groups)
    if _GROUP_GENERIC in groups:
        group_order.append(_GROUP_GENERIC)

    printed_count = 0
    current_index = start_index

    for group_name in group_order:
        if printed_count >= limit:
            break
        items = groups.get(group_name, [])
        if not items:
            continue

        style = "[bold]" if group_name != _GROUP_GENERIC else "[bold dim]"
        console.print(f"{style}{escape(group_name)}:[/]")

        for nm in items:
            if printed_count >= limit:
                break
            count_suffix = ""
            if nm.snippets:
                plural = "es" if len(nm.snippets) > 1 else ""
                count_suffix = f" [dim]({len(nm.snippets)} match{plural})[/]"
            nm_meta = (
                _format_file_meta(nm.path)
                + count_suffix
                + (f" [dim]({nm.handler}, confidence: {nm.confidence:.2f})[/]" if verbose else "")
            )
            color = "cyan" if group_name != _GROUP_GENERIC else "dim cyan"
            console.print(f"  {current_index}. [{color}]{escape(str(nm.path))}[/]{nm_meta}")
            if nm.snippets:
                for line_num, snippet_text in nm.snippets:
                    formatted_snippet = _format_snippet(snippet_text, query)
                    console.print(f"    [dim]└─ L{line_num}:[/] {formatted_snippet}")
            printed_count += 1
            current_index += 1

    return current_index
