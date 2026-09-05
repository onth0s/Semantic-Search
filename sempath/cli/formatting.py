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
    from sempath.utils.file_ops import format_human_size

    return format_human_size(size_bytes)


def _human_mtime(mtime: float) -> str:
    """Format a modification timestamp as a human-readable date-time string."""
    from sempath.utils.file_ops import format_human_mtime

    return format_human_mtime(mtime)


def _format_file_meta(path: Path) -> str:
    """Return a compact '[size, date]' dimmed suffix for *path*."""
    from sempath.utils.file_ops import get_path_file_meta

    return get_path_file_meta(path)


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


def get_ordered_display_matches(
    matches: list,
    search_root: Path,
    limit: int | None = None,
) -> list:
    """Return *matches* ordered exactly as grouped for console display, up to *limit*."""
    from collections import defaultdict

    content_matches = [m for m in matches if getattr(m, "snippets", None)]
    path_matches = [m for m in matches if not getattr(m, "snippets", None)]

    ordered: list = []

    def _collect_partition(partition_items: list) -> None:
        groups: dict[str, list] = defaultdict(list)
        for nm in partition_items:
            group_lbl = _classify_match(nm.path, search_root)
            groups[group_lbl].append(nm)

        group_order = []
        seen_groups = set()
        for nm in partition_items:
            group_lbl = _classify_match(nm.path, search_root)
            if group_lbl != _GROUP_GENERIC and group_lbl not in seen_groups:
                seen_groups.add(group_lbl)
                group_order.append(group_lbl)

        if _GROUP_GENERIC in groups:
            group_order.append(_GROUP_GENERIC)

        for group_name in group_order:
            if limit is not None and len(ordered) >= limit:
                break
            items = groups.get(group_name, [])
            for nm in items:
                if limit is not None and len(ordered) >= limit:
                    break
                ordered.append(nm)

    if content_matches:
        _collect_partition(content_matches)
        if path_matches and (limit is None or len(ordered) < limit):
            _collect_partition(path_matches)
    else:
        _collect_partition(matches)

    return ordered


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

    # Partition matches into content-based (with snippets) and filename/metadata-based
    content_matches = [m for m in matches if getattr(m, "snippets", None)]
    path_matches = [m for m in matches if not getattr(m, "snippets", None)]

    printed_count = 0
    current_index = start_index

    def _render_partition(partition_items: list, header_prefix: str = "") -> None:
        nonlocal printed_count, current_index
        groups: dict[str, list] = defaultdict(list)
        for nm in partition_items:
            group_lbl = _classify_match(nm.path, search_root)
            groups[group_lbl].append(nm)

        # Order groups by the first appearance of each group in the ranked candidate list
        group_order = []
        seen_groups = set()
        for nm in partition_items:
            group_lbl = _classify_match(nm.path, search_root)
            if group_lbl != _GROUP_GENERIC and group_lbl not in seen_groups:
                seen_groups.add(group_lbl)
                group_order.append(group_lbl)

        if _GROUP_GENERIC in groups:
            group_order.append(_GROUP_GENERIC)

        for group_name in group_order:
            if printed_count >= limit:
                break
            items = groups.get(group_name, [])
            if not items:
                continue

            style = "[bold]" if group_name != _GROUP_GENERIC else "[bold dim]"
            display_name = f"{header_prefix}{group_name}" if header_prefix else group_name
            console.print(f"{style}{escape(display_name)}:[/]")

            for nm in items:
                if printed_count >= limit:
                    break
                count_suffix = ""
                if nm.snippets:
                    plural = "es" if len(nm.snippets) > 1 else ""
                    count_suffix = f" [dim]({len(nm.snippets)} match{plural})[/]"
                handler_meta = (
                    f" [dim]({nm.handler}, confidence: {nm.confidence:.2f})[/]" if verbose else ""
                )
                nm_meta = _format_file_meta(nm.path) + count_suffix + handler_meta
                color = "cyan" if group_name != _GROUP_GENERIC else "dim cyan"
                console.print(f"  {current_index}. [{color}]{escape(str(nm.path))}[/]{nm_meta}")
                if nm.snippets:
                    for line_num, snippet_text in nm.snippets:
                        formatted_snippet = _format_snippet(snippet_text, query)
                        console.print(f"    [dim]└─ L{line_num}:[/] {formatted_snippet}")
                printed_count += 1
                current_index += 1

    if content_matches:
        _render_partition(content_matches)
        if path_matches and printed_count < limit:
            console.print("[dim]─" * 40 + " [bold yellow]Filename Matches[/] " + "─" * 40 + "[/]")
            _render_partition(path_matches)
    else:
        _render_partition(matches)

    return current_index
