"""Tests for sempath.models — MatchResult and SearchResult."""

from pathlib import Path

from sempath.models import MatchResult, SearchResult


class TestMatchResult:
    """Tests for the MatchResult NamedTuple."""

    def test_creation_with_valid_fields(self):
        """MatchResult can be created with valid path, confidence, and handler."""
        result = MatchResult(
            path=Path("C:/Users/Leonardo/Desktop/__MAIN"),
            confidence=0.95,
            handler="h1_exact",
        )
        assert result.path == Path("C:/Users/Leonardo/Desktop/__MAIN")
        assert result.confidence == 0.95
        assert result.handler == "h1_exact"

    def test_access_named_fields(self):
        """Named fields are accessible via attribute access."""
        result = MatchResult(
            path=Path("/tmp/test"),
            confidence=0.75,
            handler="h4_fuzzy",
        )
        assert isinstance(result.path, Path)
        assert isinstance(result.confidence, float)
        assert isinstance(result.handler, str)

    def test_is_tuple(self):
        """MatchResult behaves as a tuple (NamedTuple)."""
        result = MatchResult(
            path=Path("/some/path"),
            confidence=1.0,
            handler="h1_exact",
        )
        assert len(result) == 3
        assert result[0] == Path("/some/path")
        assert result[1] == 1.0
        assert result[2] == "h1_exact"


class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_success_to_dict(self):
        """SearchResult with status='success' serializes correctly via to_dict()."""
        match = MatchResult(
            path=Path("C:/Users/Leonardo/Desktop/__MAIN"),
            confidence=1.0,
            handler="h1_exact",
        )
        sr = SearchResult(
            status="success",
            query="desktop/main",
            match=match,
            near_misses=[],
            message="",
        )
        d = sr.to_dict()
        assert d["status"] == "success"
        assert d["query"] == "desktop/main"
        assert d["match"]["confidence"] == 1.0
        assert d["match"]["handler"] == "h1_exact"

    def test_ambiguous_includes_near_misses(self):
        """SearchResult with status='ambiguous' includes near_misses in to_dict()."""
        near1 = MatchResult(
            path=Path("C:/Users/Leonardo/Desktop/__MAIN"),
            confidence=0.85,
            handler="h4_fuzzy",
        )
        near2 = MatchResult(
            path=Path("C:/Users/Leonardo/Downloads"),
            confidence=0.35,
            handler="h7_embedding",
        )
        sr = SearchResult(
            status="ambiguous",
            query="dsktp/maine",
            match=None,
            near_misses=[near1, near2],
            message="No match found above confidence threshold.",
        )
        d = sr.to_dict()
        assert d["status"] == "ambiguous"
        assert len(d["near_misses"]) == 2
        assert d["near_misses"][0]["handler"] == "h4_fuzzy"
        assert d["near_misses"][1]["handler"] == "h7_embedding"
        assert d["message"] == "No match found above confidence threshold."

    def test_failed_with_empty_near_misses(self):
        """SearchResult with status='failed' and empty near_misses serializes correctly."""
        sr = SearchResult(
            status="failed",
            query="unknown_file_query",
            match=None,
            near_misses=[],
            message="No candidate paths or near-misses matched the query.",
        )
        d = sr.to_dict()
        assert d["status"] == "failed"
        assert d["query"] == "unknown_file_query"
        assert d["near_misses"] == []
        assert d["message"] == "No candidate paths or near-misses matched the query."

    def test_to_dict_converts_paths_to_strings(self):
        """to_dict() converts Path objects to strings for JSON serialization."""
        match = MatchResult(
            path=Path("C:/Users/Leonardo/Desktop/__MAIN"),
            confidence=1.0,
            handler="h1_exact",
        )
        sr = SearchResult(
            status="success",
            query="main",
            match=match,
            near_misses=[],
            message="",
        )
        d = sr.to_dict()
        # The match path should be a string, not a Path object
        assert isinstance(d["match"]["path"], str)

    def test_to_dict_near_miss_paths_are_strings(self):
        """to_dict() converts near-miss Path objects to strings."""
        near = MatchResult(
            path=Path("C:/Users/Leonardo/Downloads"),
            confidence=0.4,
            handler="h3_token_normalized",
        )
        sr = SearchResult(
            status="ambiguous",
            query="dl",
            match=None,
            near_misses=[near],
            message="Ambiguous.",
        )
        d = sr.to_dict()
        assert isinstance(d["near_misses"][0]["path"], str)
