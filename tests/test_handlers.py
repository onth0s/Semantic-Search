"""Unit tests for matching handlers H1 through H4."""

from pathlib import Path

import pytest

from src.handlers.h1_exact import ExactMatchHandler
from src.handlers.h2_case_insensitive import CaseInsensitiveHandler
from src.handlers.h3_token_normalized import TokenNormalizedHandler
from src.handlers.h4_fuzzy import FuzzyMatchHandler


@pytest.fixture
def mock_candidates() -> list[Path]:
    """Provide a list of Path objects for matching tests."""
    return [
        Path("C:/User/Desktop/__MAIN"),
        Path("C:/User/Desktop/docs"),
        Path("C:/User/Desktop/docs/notes.txt"),
        Path("C:/User/Documents/notes.txt"),
        Path("C:/User/Downloads"),
        Path("C:/User/Downloads/MyProject"),
        Path("C:/User/Downloads/my_project"),
    ]


class TestH1Exact:
    """Tests for H1 ExactMatchHandler."""

    def test_exact_name_match(self, sample_config: dict, mock_candidates: list[Path]):
        handler = ExactMatchHandler(sample_config)
        # Match by exact filename
        res = handler.match("notes.txt", mock_candidates)
        assert res is not None
        assert res.confidence == 1.0
        assert res.handler == "h1_exact"

    def test_exact_stem_match(self, sample_config: dict, mock_candidates: list[Path]):
        handler = ExactMatchHandler(sample_config)
        # Match by exact filename without extension
        res = handler.match("notes", mock_candidates)
        assert res is not None
        assert res.path.name == "notes.txt"

    def test_exact_path_suffix_match(self, sample_config: dict, mock_candidates: list[Path]):
        handler = ExactMatchHandler(sample_config)
        # Match using subpath separators
        res = handler.match("Desktop/__MAIN", mock_candidates)
        assert res is not None
        assert res.path == Path("C:/User/Desktop/__MAIN")

    def test_tie_breaker_shortest_depth(self, sample_config: dict):
        handler = ExactMatchHandler(sample_config)
        candidates = [
            Path("C:/User/Desktop/docs/notes.txt"),  # Depth 5
            Path("C:/User/notes.txt"),  # Depth 3 (closer to root)
        ]
        res = handler.match("notes.txt", candidates)
        assert res is not None
        assert res.path == Path("C:/User/notes.txt")


class TestH2CaseInsensitive:
    """Tests for H2 CaseInsensitiveHandler."""

    def test_case_insensitive_name_match(self, sample_config: dict, mock_candidates: list[Path]):
        handler = CaseInsensitiveHandler(sample_config)
        res = handler.match("NOTES.txt", mock_candidates)
        assert res is not None
        assert res.confidence == 0.95
        assert res.handler == "h2_case_insensitive"

    def test_case_insensitive_stem_match(self, sample_config: dict, mock_candidates: list[Path]):
        handler = CaseInsensitiveHandler(sample_config)
        res = handler.match("myproject", mock_candidates)
        assert res is not None
        assert res.path.name == "MyProject"


class TestH3TokenNormalized:
    """Tests for H3 TokenNormalizedHandler."""

    def test_token_normalized_match(self, sample_config: dict, mock_candidates: list[Path]):
        handler = TokenNormalizedHandler(sample_config)
        # Match by changing token ordering/separator
        res = handler.match("my-project", mock_candidates)
        assert res is not None
        assert res.confidence == 0.9
        assert res.handler == "h3_token_normalized"
        assert res.path.name == "my_project"

    def test_token_normalized_subpath(self, sample_config: dict, mock_candidates: list[Path]):
        handler = TokenNormalizedHandler(sample_config)
        # Match multi-part queries
        res = handler.match("desktop/main", mock_candidates)
        assert res is not None
        assert res.path == Path("C:/User/Desktop/__MAIN")


class TestH4Fuzzy:
    """Tests for H4 FuzzyMatchHandler."""

    def test_fuzzy_match_above_threshold(self, sample_config: dict, mock_candidates: list[Path]):
        handler = FuzzyMatchHandler(sample_config)
        # "dwl" is similar to "Downloads" (~60%) but "downloads" is fuzzy match
        # Let's try spelling mistakes: "dwnloads" vs "Downloads"
        res = handler.match("dwnloads", mock_candidates)
        assert res is not None
        assert res.handler == "h4_fuzzy"
        assert res.confidence > 0.75

    def test_fuzzy_match_below_threshold(self, sample_config: dict, mock_candidates: list[Path]):
        handler = FuzzyMatchHandler(sample_config)
        # Completely unrelated, should not match
        res = handler.match("unrelatedabc", mock_candidates)
        assert res is None
