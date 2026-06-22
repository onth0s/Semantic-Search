"""Embedding handler — semantic match via sentence-transformers.

Lazy-loads a sentence-transformer model to encode the query and
candidate basenames into dense vector representations. Computes
cosine similarity between the query embedding and each candidate
embedding, returning the best match.
Returns a MatchResult with confidence equal to cosine_sim.
"""

from __future__ import annotations

from pathlib import Path

import click

from src.handlers.base import BaseHandler
from src.models import MatchResult
from src.utils.console import err_console


class EmbeddingHandler(BaseHandler):
    """Semantic match via lazy-loaded sentence-transformers."""

    name: str = "h7_embedding"
    _model = None

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt a semantic embedding match against candidate basenames."""
        if not query or not candidates:
            return None

        # Check interactive mode
        ctx = click.get_current_context(silent=True)
        non_interactive = False
        if ctx:
            non_interactive = ctx.obj.get("non_interactive", False)

        # Show prompt before running heavy ML matching (if interactive)
        if not non_interactive:
            err_console.print(
                "\n[bold yellow]No quick match found.[/] "
                "Fallback to Deep Semantic Search ([cyan]sentence-transformers[/])?"
            )
            err_console.print("[dim]This may take 1-2 seconds.[/]")
            confirm = click.confirm("Continue", default=True, err=True)
            if not confirm:
                return None

        # Lazy load sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer, util
        except ImportError:
            err_console.print(
                "[bold yellow]Warning:[/] [cyan]sentence-transformers[/] is not installed."
            )
            err_console.print(
                "To enable semantic matches, run "
                "[bold]pip install -e .[semantic][/bold] from this checkout or "
                "[bold]pip install sempath[semantic][/bold] for an installed package."
            )
            return None

        # Load/cache the model
        model_name = self.config.get("handlers", {}).get("h7_model", "all-MiniLM-L6-v2")
        if self._model is None:
            try:
                if ctx and ctx.obj.get("verbose"):
                    err_console.print(f"[dim]Loading embedding model '{model_name}'...[/]")
                self._model = SentenceTransformer(model_name)
            except Exception as exc:
                err_console.print(f"[bold red]Error loading embedding model:[/] {exc}")
                return None

        # Embed query and candidate basenames (or stems)
        # Use p.stem as it represents the semantic filename without extension
        candidate_texts = [p.stem for p in candidates]
        try:
            query_emb = self._model.encode(query, convert_to_tensor=True)
            candidate_embs = self._model.encode(candidate_texts, convert_to_tensor=True)

            # Compute cosine similarities
            cosine_scores = util.cos_sim(query_emb, candidate_embs)[0]

            # Find the best match
            best_idx = int(cosine_scores.argmax())
            best_score = float(cosine_scores[best_idx])

            return MatchResult(candidates[best_idx], best_score, self.name)
        except Exception as exc:
            if ctx and ctx.obj.get("verbose"):
                err_console.print(f"[dim]Embedding match failed: {exc}[/]")
            return None
