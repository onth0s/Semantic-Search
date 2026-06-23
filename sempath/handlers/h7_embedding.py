"""Embedding handler — semantic match via sentence-transformers.

Lazy-loads a sentence-transformer model to encode the query and
candidate basenames into dense vector representations. Computes
cosine similarity between the query embedding and each candidate
embedding, returning the best match.
Returns a MatchResult with confidence equal to cosine_sim.
"""

from __future__ import annotations

import re
from pathlib import Path

import click

from sempath.handlers.base import BaseHandler
from sempath.models import MatchResult
from sempath.utils.console import err_console


class EmbeddingHandler(BaseHandler):
    """Semantic match via lazy-loaded sentence-transformers."""

    name: str = "h7_embedding"
    _model = None

    def _compute_similarities(
        self, query: str, candidates: list[Path]
    ) -> list[tuple[Path, float]] | None:
        """Compute cosine similarity between query and candidate stems."""
        if not query or not candidates:
            return None

        # Check interactive mode
        ctx = click.get_current_context(silent=True)
        non_interactive = True
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
        import os

        os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
        os.environ["HF_HUB_VERBOSITY"] = "error"
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        try:
            from huggingface_hub.utils import disable_progress_bars

            disable_progress_bars()
        except ImportError:
            pass

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
                from sempath.utils.logging import verbose_log

                verbose_log(f"[dim]Loading embedding model '{model_name}'...[/]")
                self._model = SentenceTransformer(model_name)
            except Exception as exc:
                err_console.print(f"[bold red]Error loading embedding model:[/] {exc}")
                return None

        # Embed relative path from search root so parent folder names contribute
        # e.g. "3D-to-reGEN-to-VID/Katsuragi Misato" instead of just "Misato"
        ctx = click.get_current_context(silent=True)
        search_root = ctx.obj.get("root", Path(".")) if ctx else Path(".")

        def _candidate_text(p: Path) -> str:
            try:
                rel = p.relative_to(search_root)
            except ValueError:
                rel = p
            return re.sub(r"[\\/._\-]+", " ", str(rel)).strip()

        candidate_texts = [_candidate_text(p) for p in candidates]
        try:
            from sempath.heuristics import translate_wildcards

            translated_query = translate_wildcards(query)
            query_emb = self._model.encode(
                translated_query, convert_to_tensor=True, show_progress_bar=False
            )
            candidate_embs = self._model.encode(
                candidate_texts, convert_to_tensor=True, show_progress_bar=False
            )

            # Compute cosine similarities
            cosine_scores = util.cos_sim(query_emb, candidate_embs)[0]

            results = []
            for i, p in enumerate(candidates):
                score = float(cosine_scores[i])
                results.append((p, score))
            return results

        except Exception as exc:
            from sempath.utils.logging import verbose_log

            verbose_log(f"[dim]Embedding match failed: {exc}[/]")
            return None

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt a semantic embedding match against candidate basenames."""
        results = self._compute_similarities(query, candidates)
        if not results:
            return None
        # Find the best match
        best_candidate, best_score = max(results, key=lambda x: x[1])
        if best_score < 0.5:
            return None
        return MatchResult(best_candidate, best_score, self.name)

    def match_all(self, query: str, candidates: list[Path]) -> list[MatchResult]:
        """Attempt to match the query and return all matches >= 0.5 similarity."""
        results = self._compute_similarities(query, candidates)
        if not results:
            return []

        matches = []
        for p, score in results:
            if score >= 0.5:
                matches.append(MatchResult(p, score, self.name))

        matches.sort(key=lambda m: -m.confidence)
        return matches
