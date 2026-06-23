"""Base handler interface for the Chain of Responsibility pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from src.models import MatchResult


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

    def handle(self, query: str, candidates: list[Path]) -> list[MatchResult]:
        """Execute this handler, falling through to the next if no match."""
        import click
        ctx = click.get_current_context(silent=True)
        verbose = ctx.obj.get("verbose", False) if ctx else False

        if verbose:
            from src.utils.console import err_console
            err_console.print(f"[dim]Evaluating handler [bold cyan]{self.name}[/] on {len(candidates)} candidates...[/]")

        results = self.match_all(query, candidates)
        if results:
            if verbose:
                from src.utils.console import err_console
                err_console.print(f"[bold green]✔ Handler {self.name} matched {len(results)} items (confidence range: {min(r.confidence for r in results):.2f}-{max(r.confidence for r in results):.2f})[/]")
            return results

        if verbose:
            from src.utils.console import err_console
            err_console.print(f"[yellow]✗ Handler {self.name} returned no match.[/]")

        if self.next_handler is not None:
            return self.next_handler.handle(query, candidates)
        return []

