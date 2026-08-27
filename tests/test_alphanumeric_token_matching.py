"""Unit tests for alphanumeric boundary tokenization and matching."""

from __future__ import annotations

from pathlib import Path

from sempath.engine import SearchEngine
from sempath.handlers.h3_token_normalized import TokenNormalizedHandler
from sempath.handlers.h4_fuzzy import FuzzyMatchHandler
from sempath.utils.tokenize import normalize_tokens, normalize_tokens_with_wildcards


def test_normalize_tokens_alphanumeric():
    """Verify normalize_tokens splits letter-digit boundaries."""
    assert normalize_tokens("paper1") == {"paper", "1"}
    assert normalize_tokens("paper_1") == {"paper", "1"}
    assert normalize_tokens("paper-1") == {"paper", "1"}
    assert normalize_tokens("10serial") == {"10", "serial"}
    assert normalize_tokens("v2") == {"v", "2"}


def test_normalize_tokens_with_wildcards_alphanumeric():
    """Verify normalize_tokens_with_wildcards splits letter-digit boundaries."""
    assert normalize_tokens_with_wildcards("paper1") == {"paper", "1"}
    assert normalize_tokens_with_wildcards("paper1*") == {"paper", "1*"}


def test_h3_token_normalized_matches_paper1(sample_config: dict):
    """Verify TokenNormalizedHandler matches 'paper1' to multi-word filenames."""
    handler = TokenNormalizedHandler(sample_config)
    candidate = Path("docs/paper_1_psychological_wellbeing_bdsm.html")
    other_candidate = Path("docs/paper_2_consensual_power_exchange.html")

    match = handler.match("paper1", [candidate, other_candidate])
    assert match is not None
    assert match.path == candidate
    assert match.confidence >= 0.90


def test_h4_fuzzy_matches_paper1(sample_config: dict):
    """Verify FuzzyMatchHandler calculates high token_set similarity for 'paper1'."""
    handler = FuzzyMatchHandler(sample_config)
    candidate = Path("docs/paper_1_psychological_wellbeing_bdsm.html")

    match = handler.match("paper1", [candidate])
    assert match is not None
    assert match.path == candidate
    assert match.confidence >= 0.75


def test_search_engine_find_path_paper1(sample_config: dict, tmp_path: Path):
    """End-to-end test for searching 'paper1' across multi-word filenames."""
    engine = SearchEngine(sample_config)

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)

    f1 = docs_dir / "paper_1_psychological_wellbeing_bdsm.html"
    f1.write_text("<html>Paper 1</html>", encoding="utf-8")

    f2 = docs_dir / "paper_2_consensual_power_exchange.html"
    f2.write_text("<html>Paper 2</html>", encoding="utf-8")

    f3 = docs_dir / "paper_3_bdsm_motivations.html"
    f3.write_text("<html>Paper 3</html>", encoding="utf-8")

    res = engine.find_path("paper1", tmp_path, no_index=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path == f1
