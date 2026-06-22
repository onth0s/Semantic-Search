"""Interactive handler — user selection fallback.

Presents top ambiguous near-miss candidates to the user for selection.
Learned confirmations are written back to memory (learned_aliases.yaml)
to automatically resolve future occurrences of the query.
"""

from __future__ import annotations

from pathlib import Path

import click
from rapidfuzz import fuzz

from src.handlers.base import BaseHandler
from src.models import MatchResult
from src.utils.memory import add_or_update_memory


class InteractiveHandler(BaseHandler):
    """Presents near-miss candidates for manual interactive selection."""

    name: str = "h9_interactive"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Present candidates to the user for interactive selection."""
        if not query or not candidates:
            return None

        # Check Click context for non-interactive flag
        ctx = click.get_current_context(silent=True)
        if ctx and ctx.obj.get("non_interactive", False):
            return None

        # Compute fuzzy match scores to rank candidates (similar to H4 fuzzy logic)
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

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        # Keep candidates with confidence >= 0.2 (20% similarity)
        top_candidates = [item for item in scored if item[1] >= 0.2][:5]

        if not top_candidates:
            return None

        # Print prompt to user
        click.echo("\n[?] No exact match found. Did you mean one of these?", err=True)
        for i, (path, score) in enumerate(top_candidates, start=1):
            click.echo(f"  {i}) {path} [dim](confidence: {score:.2f})[/]", err=True)
        click.echo(f"  {len(top_candidates) + 1}) [None of the above]", err=True)
        # Prompt selection
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
            # Learn this alias
            try:
                add_or_update_memory(query, selected_path)
                click.echo(
                    f"[bold green]✔ Confirmed:[/] Learned alias '{query}' -> '{selected_path}'\n"
                    f"[dim](run 'sempath alias undo' to revert)[/]",
                    err=True,
                )
            except Exception as exc:
                if ctx and ctx.obj.get("verbose"):
                    click.echo(f"[dim]Failed to save learned memory: {exc}[/]", err=True)

            return MatchResult(selected_path, 1.0, self.name)

        return None
