"""Unit tests for fuzzy matching on multi-token and compound file names."""

from __future__ import annotations

from pathlib import Path

from sempath.engine import SearchEngine
from sempath.handlers.h4_fuzzy import FuzzyMatchHandler


def test_h4_fuzzy_multitoken_typo(sample_config: dict):
    """Test H4 directly matches multi-token strings with typos."""
    handler = FuzzyMatchHandler(sample_config)

    candidates = [
        Path("C:/project/logs/formal_verification_latest.log"),
        Path("C:/project/scripts/compile_formal_verification_logs.py"),
        Path("C:/project/docs/readme.txt"),
    ]

    matches = handler.match_all("formal_verificatiom", candidates)
    matched_paths = [m.path for m in matches]
    assert Path("C:/project/logs/formal_verification_latest.log") in matched_paths
    assert Path("C:/project/scripts/compile_formal_verification_logs.py") in matched_paths
    assert Path("C:/project/docs/readme.txt") not in matched_paths


def test_engine_multitoken_fuzzy_search(sample_config: dict, tmp_path: Path):
    """Test SearchEngine end-to-end matching on multi-token typo query."""
    engine = SearchEngine(sample_config)

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True)
    f_log = logs_dir / "formal_verification_latest.log"
    f_log.write_text("log content")

    res = engine.find_path("formal_verificatiom", tmp_path, no_index=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path == f_log
