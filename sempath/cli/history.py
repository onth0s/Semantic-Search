"""History commands: list last search matches and recall a match by rank.

Implements:
- ``sempath list`` — show numbered matches from the last search snapshot.
- ``sempath get N`` — comprehensive view of match N and copy it to the clipboard.
- ``sempath N`` — lean form routed to ``get N --bare``: prints the raw path
  and copies it to the clipboard (pipe-able, e.g. ``cd (sempath 2)``).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.markup import escape

from sempath.cli.formatting import _format_elapsed_time, _format_file_meta, _human_size
from sempath.utils.clipboard import copy_to_clipboard
from sempath.utils.console import console, err_console
from sempath.utils.history import history_matches, load_history


def _format_history_timestamp(timestamp: str) -> str:
    """Format an ISO timestamp as 'YYYY-MM-DD HH:MM'."""
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return timestamp
    return dt.strftime("%Y-%m-%d %H:%M")


def _get_match(history: dict | None, n: int) -> dict | None:
    """Return the 1-indexed match at rank *n* from a history snapshot."""
    matches = history_matches(history)
    if not matches or not (1 <= n <= len(matches)):
        return None
    return matches[n - 1]


def _resolve_match_path(match: dict) -> Path:
    """Return the Path for a history match entry."""
    return Path(str(match.get("path", "")))


def _print_no_history() -> None:
    """Print the 'no previous search' notice and exit."""
    err_console.print(
        "[bold yellow]No previous search found.[/] Run [bold cyan]'sempath find QUERY'[/] first."
    )
    sys.exit(1)


def register_history_commands(cli_group: click.Group) -> None:
    """Register the list and get commands on the main CLI group."""

    @cli_group.command("list")
    @click.option(
        "--json",
        "json_output",
        is_flag=True,
        default=False,
        help="Output structured JSON instead of styled text.",
    )
    def list_matches(json_output: bool) -> None:
        """List the matches from the last search."""
        history = load_history()
        matches = history_matches(history)

        if not matches:
            _print_no_history()

        if json_output:
            click.echo(json.dumps(matches, indent=2, ensure_ascii=False))
            sys.exit(0)

        query = history.get("query", "")
        timestamp = _format_history_timestamp(history.get("timestamp", ""))
        elapsed = float(history.get("elapsed_seconds", 0.0))
        elapsed_str = f" [dim](in {_format_elapsed_time(elapsed)})[/]" if elapsed > 0 else ""
        console.print(
            f"[bold]Last search:[/] [bold cyan]{escape(query)}[/] "
            f"[dim]at {timestamp}[/]{elapsed_str}"
        )
        console.print(f"[dim]{len(matches)} result(s):[/]")
        for idx, match in enumerate(matches, start=1):
            path = _resolve_match_path(match)
            meta = _format_file_meta(path)
            console.print(f"  {idx}. [cyan]{escape(str(path))}[/]{meta}")

    @cli_group.command("get")
    @click.argument("n", default=1, type=int)
    @click.option(
        "--json",
        "json_output",
        is_flag=True,
        default=False,
        help="Output structured JSON instead of styled text.",
    )
    @click.option(
        "--no-copy",
        is_flag=True,
        default=False,
        help="Do not copy the path to the clipboard.",
    )
    @click.option(
        "--bare",
        is_flag=True,
        default=False,
        hidden=True,
        help="Lean output: print only the raw path and copy it.",
    )
    def get_match(n: int, json_output: bool, no_copy: bool, bare: bool) -> None:
        """Recall match N from the last search and copy its path to the clipboard."""
        history = load_history()
        matches = history_matches(history)
        if not matches:
            _print_no_history()

        match = _get_match(history, n)
        if match is None:
            err_console.print(
                f"[bold red]Invalid rank:[/] {n} — last search returned {len(matches)} result(s)."
            )
            sys.exit(1)

        path = _resolve_match_path(match)
        path_str = str(path)

        if not no_copy:
            copy_to_clipboard(path_str)

        if bare:
            click.echo(path_str)
            sys.exit(0)

        if json_output:
            click.echo(json.dumps(match, indent=2, ensure_ascii=False))
            sys.exit(0)

        query = history.get("query", "")
        matches = history_matches(history)
        rank = int(match.get("rank", n))
        total = len(matches)
        handler = match.get("handler", "")
        confidence = float(match.get("confidence", 0.0))
        exists = path.exists()

        console.print(f"[bold]Last search:[/] [bold cyan]{escape(query)}[/]")
        console.print(
            f"[bold]Match {rank}[/] [dim]of {total}[/] "
            f"[dim]→ ({handler}, confidence: {confidence:.2f})[/]"
        )

        if not exists:
            console.print("[dim red]⚠ Path no longer exists[/]")

        try:
            st = path.stat()
            kind = "directory" if path.is_dir() else "file"
            size = _human_size(st.st_size) if not path.is_dir() else "DIR"
            mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
        except OSError:
            kind = "unknown"
            size = "-"
            mtime = "-"

        console.print(f"  [dim]Kind:[/]     {kind}")
        console.print(f"  [dim]Size:[/]     {size}")
        console.print(f"  [dim]Modified:[/] {mtime}")
        console.print(f"  [dim]Path:[/]     [bold cyan]{escape(path_str)}[/]")
        console.print(f"  [dim]Query:[/]    {escape(query)}")

        if match.get("snippets"):
            from sempath.cli.formatting import _format_snippet

            for line_num, snippet_text in match["snippets"]:
                console.print(f"  [dim]└─ L{line_num}:[/] {_format_snippet(snippet_text, query)}")

        if no_copy:
            console.print("[dim](clipboard copy skipped — --no-copy)[/]")
        else:
            console.print(f"[bold green]✔ Copied to clipboard:[/] [bold]{escape(path_str)}[/]")

        if not exists:
            err_console.print(
                "[bold yellow]Tip:[/] the stored path no longer exists; re-run "
                "[bold cyan]'sempath find'[/] to refresh results."
            )
            sys.exit(1)
