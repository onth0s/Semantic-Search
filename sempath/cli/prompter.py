"""CLI interactive prompt and confirmation flows for sempath."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
from rich.markup import escape

from sempath.cli.formatting import _format_file_meta
from sempath.utils.console import err_console

if TYPE_CHECKING:
    from sempath.models import MatchResult


def prompt_disambiguation_selection(
    near_misses: list[MatchResult],
    verbose: bool = False,
) -> MatchResult | None:
    """Render top ambiguous matches and prompt the user to pick one or choose None.

    Returns the chosen MatchResult, or None if the user picked 'None of the above'.
    Raises click.Abort if the user canceled the prompt.
    """
    top_candidates = list(near_misses)[:5]
    err_console.print("\n[bold yellow]?[/] No exact match found. Did you mean one of these?")
    for idx, nm in enumerate(top_candidates, start=1):
        nm_meta = _format_file_meta(nm.path)
        if verbose:
            nm_meta += f" [dim]({nm.handler}, confidence: {nm.confidence:.2f})[/]"
        err_console.print(f"  {idx}. [cyan]{escape(str(nm.path))}[/]{nm_meta}")
    err_console.print(f"  {len(top_candidates) + 1}. [dim]None of the above[/]")

    selection = click.prompt(
        f"Select an option (1-{len(top_candidates) + 1})",
        type=int,
        default=len(top_candidates) + 1,
        show_default=True,
        err=True,
    )

    if 1 <= selection <= len(top_candidates):
        return top_candidates[selection - 1]
    return None
