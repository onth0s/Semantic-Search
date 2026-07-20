"""Tests for sempath.chain — build_chain and handler chain wiring."""

from pathlib import Path

from sempath.chain import build_chain
from sempath.handlers.base import BaseHandler


def _count_chain_length(head: BaseHandler) -> int:
    """Count the number of handlers in a chain by following next_handler links."""
    count = 0
    current = head
    while current is not None:
        count += 1
        current = getattr(current, "next_handler", None)
    return count


def _get_handler_names(head: BaseHandler) -> list[str]:
    """Collect handler class names by walking the chain."""
    names: list[str] = []
    current = head
    while current is not None:
        names.append(type(current).__name__)
        current = getattr(current, "next_handler", None)
    return names


class TestBuildChainAllHandlers:
    """Tests for build_chain with all handlers enabled."""

    def test_returns_valid_base_handler(self, sample_config: dict):
        """build_chain with all handlers enabled returns a valid BaseHandler."""
        head = build_chain(sample_config)
        assert isinstance(head, BaseHandler)

    def test_chain_has_correct_length(self, sample_config: dict):
        """Chain has correct length (8 handlers) when all are enabled."""
        head = build_chain(sample_config)
        length = _count_chain_length(head)
        assert length == 8

    def test_first_handler_is_h1(self, sample_config: dict):
        """First handler in chain is h1 when all are enabled."""
        head = build_chain(sample_config)
        # The first handler's class name should reference h1 / exact
        class_name = type(head).__name__.lower()
        assert "h1" in class_name or "exact" in class_name


class TestBuildChainSubset:
    """Tests for build_chain with a subset of handlers."""

    def test_subset_wires_only_specified_handlers(self, sample_config: dict):
        """build_chain with subset of handlers wires only those handlers."""
        sample_config["handlers"]["enabled"] = ["h1", "h2"]
        head = build_chain(sample_config)
        length = _count_chain_length(head)
        assert length == 2

    def test_subset_chain_first_is_h1(self, sample_config: dict):
        """First handler is h1 even with subset ['h1', 'h2']."""
        sample_config["handlers"]["enabled"] = ["h1", "h2"]
        head = build_chain(sample_config)
        class_name = type(head).__name__.lower()
        assert "h1" in class_name or "exact" in class_name

    def test_single_handler_chain(self, sample_config: dict):
        """build_chain with a single handler produces a chain of length 1."""
        sample_config["handlers"]["enabled"] = ["h1"]
        head = build_chain(sample_config)
        length = _count_chain_length(head)
        assert length == 1
        assert head.next_handler is None


class TestChainDelegation:
    """Tests for chain delegation (handle method)."""

    def test_handle_with_no_matching_returns_empty_list(self, sample_config: dict):
        """Calling handle() on the head with no matching candidates returns an empty list."""
        # Use only fast, deterministic handlers to avoid heavy imports
        sample_config["handlers"]["enabled"] = ["h1", "h2"]
        head = build_chain(sample_config)

        # Query that won't match any candidate
        result = head.handle("nonexistent_gibberish_xyz", [Path("/tmp/unrelated")])
        assert result == []

    def test_handle_returns_match_result_on_exact(self, sample_config: dict, mock_fs_path: Path):
        """Calling handle() returns a MatchResult when an exact match exists."""
        sample_config["handlers"]["enabled"] = ["h1"]
        head = build_chain(sample_config)

        # Create a candidate that exactly matches the query
        target = mock_fs_path / "Desktop"
        result = head.handle("Desktop", [target])
        assert len(result) == 1
        assert result[0].path == target
        assert result[0].confidence == 1.0
