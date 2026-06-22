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

    def handle(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Execute this handler, falling through to the next if no match."""
        result = self.match(query, candidates)
        if result is not None:
            return result
        if self.next_handler is not None:
            return self.next_handler.handle(query, candidates)
        return None
