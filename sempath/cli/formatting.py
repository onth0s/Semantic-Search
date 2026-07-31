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
) -> None:
    """Print *matches* (up to *limit*) sorted into display groups."""
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
            console.print(f"  - [{color}]{escape(str(nm.path))}[/]{nm_meta}")
            if nm.snippets:
                for line_num, snippet_text in nm.snippets:
                    console.print(
                        f"    [dim]└─ L{line_num}:[/] [dim green]{escape(snippet_text)}[/]"
                    )
            printed_count += 1
