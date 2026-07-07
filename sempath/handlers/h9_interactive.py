"""Interactive handler - user selection fallback.

Presents top ambiguous near-miss candidates to the user for selection.
Learned confirmations are written back to memory (learned_aliases.yaml)
to automatically resolve future occurrences of the query.
"""

from __future__ import annotations

from pathlib import Path

import click
from rapidfuzz import fuzz
from rich.markup import escape

from sempath.handlers.base import BaseHandler
from sempath.models import MatchResult
from sempath.utils.console import err_console
from sempath.utils.memory import add_or_update_memory


class InteractiveHandler(BaseHandler):
    """Presents near-miss candidates for manual interactive selection."""

    name: str = "h9_interactive"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Present candidates to the user for interactive selection."""
        if not query or not candidates:
            return None

        ctx = click.get_current_context(silent=True)
        if ctx and ctx.obj.get("non_interactive", False):
            return None

        query_lower = query.lower()
        query_parts = [part for part in query_lower.replace("\\", "/").split("/") if part]
        k = len(query_parts)

        scored = []
        for p in candidates:
            r_name = fuzz.ratio(query_lower, p.name.lower())
            r_stem = fuzz.ratio(query_lower, p.stem.lower())
            r_max = max(r_name, r_stem)

            if k > 1 and len(p.parts) >= k:
                suffix_str = "/".join(p.parts[-k:]).lower()
                r_suffix = fuzz.ratio(query_lower, suffix_str)
                r_max = max(r_max, r_suffix)

            scored.append((p, r_max / 100.0))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_candidates = [item for item in scored if item[1] >= 0.2][:5]

        if not top_candidates:
            return None

        err_console.print("\n[bold yellow]?[/] No exact match found. Did you mean one of these?")
        for i, (path, score) in enumerate(top_candidates, start=1):
            err_console.print(
                f"  {i}. [cyan]{escape(str(path))}[/] [dim](confidence: {score:.2f})[/]"
            )
        err_console.print(f"  {len(top_candidates) + 1}. [dim]None of the above[/]")

        try:
            selection = click.prompt(
                f"Select an option (1-{len(top_candidates) + 1})",
                type=int,
                default=len(top_candidates) + 1,
                show_default=True,
                err=True,
            )
        except click.Abort:
            return None

        if 1 <= selection <= len(top_candidates):
            selected_path = top_candidates[selection - 1][0]
            try:
                add_or_update_memory(query, selected_path)
                err_console.print(
                    f"[bold green]Confirmed:[/] Learned alias "
                    f"[cyan]{escape(query)}[/] -> [bold]{escape(str(selected_path))}[/]"
                )
                err_console.print("[dim](run 'sempath alias undo' to revert)[/]")
            except Exception as exc:
                from sempath.utils.logging import verbose_log

                verbose_log(f"[dim]Failed to save learned memory: {exc}[/]")

            return MatchResult(selected_path, 1.0, self.name)

        return None
