"""Base handler interface for the Chain of Responsibility pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from sempath.models import MatchResult


class BaseHandler(ABC):
    """Abstract base class for all matching handlers.

    Handlers are composed into an ordered chain. Each handler either
    returns a match with confidence, or passes to the next handler.
    """

    name: str = "base"

    def __init__(self, config: dict) -> None:
        self.config = config
        self.next_handler: BaseHandler | None = None

    def set_next(self, handler: BaseHandler) -> BaseHandler:
        """Set the next handler in the chain and return it."""
        self.next_handler = handler
        return handler

    @abstractmethod
    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt to match the query against candidates.

        Returns a MatchResult if a match is found, or None to pass
        to the next handler in the chain.
        """
        ...

    def match_all(self, query: str, candidates: list[Path]) -> list[MatchResult]:
        """Attempt to match the query against candidates and return all matches.

        Defaults to calling match() and returning a list with a single MatchResult,
        but can be overridden by subclasses for multiple match propagation.
        """
        res = self.match(query, candidates)
        return [res] if res is not None else []

    def handle(
        self,
        query: str,
        candidates: list[Path],
        collected: list[MatchResult] | None = None,
        top_n: int = 1,
    ) -> list[MatchResult]:
        """Execute this handler, accumulating matches into the collected list.

        Continues execution down the chain until the requested top_n clamp
        limit is met or until slow/interactive handlers (H7, H8, H9) are reached.
        """
        from sempath.utils.logging import verbose_log

        if collected is None:
            collected = []

        verbose_log(
            f"[dim]Evaluating handler [bold cyan]{self.name}[/] "
            f"on {len(candidates)} candidates...[/]"
        )

        results = self.match_all(query, candidates)
        if results:
            # Merge results into collected keeping higher confidence for duplicate paths
            existing = {r.path: r for r in collected}
            for r in results:
                if r.path in existing:
                    if r.confidence > existing[r.path].confidence:
                        existing[r.path] = r
                else:
                    existing[r.path] = r
            collected = list(existing.values())

            min_c = min(r.confidence for r in results)
            max_c = max(r.confidence for r in results)
            verbose_log(
                f"[bold green]✔ Handler {self.name} matched {len(results)} items "
                f"(confidence range: {min_c:.2f}-{max_c:.2f})[/]"
            )
        else:
            verbose_log(f"[yellow]✗ Handler {self.name} returned no match.[/]")

        # Check termination condition: met the top_n clamp limit
        if len(collected) >= top_n:
            return collected

        if self.next_handler is not None:
            # Cutoff before slow/interactive handlers (H7, H8, H9) if we already have matches
            if self.next_handler.name in ("h7_embedding", "h8_llm", "h9_interactive") and collected:
                verbose_log(
                    f"[dim]Cutoff before slow handler '{self.next_handler.name}' "
                    f"reached with active matches. Stopping evaluation.[/]"
                )
                return collected
            return self.next_handler.handle(query, candidates, collected, top_n=top_n)

        return collected
