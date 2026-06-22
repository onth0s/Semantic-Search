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
            confirm = click.confirm(
                "\n[!] No quick match found. Fallback to Deep Semantic Search "
                "(sentence-transformers)?\nThis may take 1-2 seconds.",
                default=True,
                err=True,
            )
            if not confirm:
                return None

        # Lazy load sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer, util
        except ImportError:
            click.echo(
                "[bold yellow]Warning:[/] 'sentence-transformers' is not installed.\n"
                "To enable semantic matches, please run: pip install sentence-transformers",
                err=True,
            )
            return None

        # Load/cache the model
        model_name = self.config.get("handlers", {}).get("h7_model", "all-MiniLM-L6-v2")
        if self._model is None:
            try:
                if ctx and ctx.obj.get("verbose"):
                    click.echo(f"[dim]Loading embedding model '{model_name}'...[/]")
                self._model = SentenceTransformer(model_name)
            except Exception as exc:
                click.echo(f"[bold red]Error loading embedding model:[/] {exc}", err=True)
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
                click.echo(f"[dim]Embedding match failed: {exc}[/]", err=True)
            return None
