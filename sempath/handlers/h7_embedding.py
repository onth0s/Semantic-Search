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

        # We embed both:
        # 1. The relative path from search root (giving parent folder context)
        # 2. The stem alone (preserving high similarity matches for target names without dilution)
        ctx = click.get_current_context(silent=True)
        search_root = ctx.obj.get("root", Path(".")) if ctx else Path(".")

        def _candidate_rel_text(p: Path) -> str:
            try:
                rel = p.relative_to(search_root)
            except ValueError:
                rel = p
            return re.sub(r"[\\/._\-]+", " ", str(rel)).strip()

        rel_texts = [_candidate_rel_text(p) for p in candidates]
        stem_texts = [p.stem for p in candidates]

        def _is_generic_stem(stem: str) -> bool:
            stem_lower = stem.lower()
            cleaned = re.sub(r"[\s\-_0-9()]+", "", stem_lower)
            return cleaned in {
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

        try:
            from sempath.heuristics import translate_wildcards

            translated_query = translate_wildcards(query)
            # BAAI/bge models require a query instruction prefix to score
            # correctly in asymmetric search.
            if "bge" in model_name.lower():
                emb_query = (
                    f"Represent this sentence for searching relevant passages: {translated_query}"
                )
            else:
                emb_query = translated_query

            query_emb = self._model.encode(
                emb_query, convert_to_tensor=True, show_progress_bar=False
            )

            # Encode all candidate texts (both relative paths and stems) in one batch
            combined_texts = rel_texts + stem_texts
            combined_embs = self._model.encode(
                combined_texts, convert_to_tensor=True, show_progress_bar=False
            )

            # Compute similarities
            scores = util.cos_sim(query_emb, combined_embs)[0]

            results = []
            num_candidates = len(candidates)
            for i, p in enumerate(candidates):
                score_rel = float(scores[i])
                score_stem = 0.0 if _is_generic_stem(p.stem) else float(scores[num_candidates + i])
                # Take the max score to keep the best of both folder context and bare name
                results.append((p, max(score_rel, score_stem)))
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
