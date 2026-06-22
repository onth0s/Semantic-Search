"""Unit tests for src.handlers.h6_alias — AliasHandler."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.handlers.h6_alias import AliasHandler


@pytest.fixture
def mock_candidates(tmp_path: Path) -> list[Path]:
    """Provide structured candidates list for alias tests."""
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    main_dir = desktop / "__MAIN"
    main_dir.mkdir()
    docs = desktop / "docs"
    docs.mkdir()

    # Create files in docs with controlled modification times
    f1 = docs / "pic1.png"
    f1.write_text("png", encoding="utf-8")
    f2 = docs / "pic2.png"
    f2.write_text("png2", encoding="utf-8")
    f3 = docs / "doc1.pdf"
    f3.write_text("pdf", encoding="utf-8")

    # Set times: f2 is newer than f1
    now = time.time()
    import os

    os.utime(f1, (now - 100, now - 100))
    os.utime(f2, (now, now))

    return [
        desktop,
        main_dir,
        docs,
        f1,
        f2,
        f3,
    ]


def test_alias_config_exact_and_fuzzy(sample_config: dict, mock_candidates: list[Path]):
    """AliasHandler matches exact and fuzzy/phonetic config keys."""
    handler = AliasHandler(sample_config)

    # 1. Exact match on config key "main" -> resolves to __MAIN
    res = handler.match("main", mock_candidates)
    assert res is not None
    assert res.path.name == "__MAIN"
    assert res.confidence == 0.95

    # 2. Fuzzy match on config key "maine" -> matches "main" -> __MAIN
    res = handler.match("maine", mock_candidates)
    assert res is not None
    assert res.path.name == "__MAIN"


def test_alias_config_regex(sample_config: dict, mock_candidates: list[Path]):
    """AliasHandler matches regex patterns in alias keys."""
    # Add regex key to configuration
    sample_config["aliases"]["^d(own)?l$"] = ["Downloads", "download"]

    # We need a candidate named Downloads
    downloads = mock_candidates[0].parent / "Downloads"
    candidates = [*mock_candidates, downloads]

    handler = AliasHandler(sample_config)

    # Query "dl" matches regex "^d(own)?l$" -> resolves to Downloads
    res = handler.match("dl", candidates)
    assert res is not None
    assert res.path.name == "Downloads"


def test_alias_learned_memory(sample_config: dict, mock_candidates: list[Path]):
    """AliasHandler matches learned aliases from memory."""
    handler = AliasHandler(sample_config)

    mock_memory = [
        {
            "query": "super_key",
            "path": str(mock_candidates[2]),  # docs folder
            "timestamp": "2026-06-22T14:10:30Z",
            "hits": 1,
            "decay_rank": 1.0,
        }
    ]

    with patch("src.utils.memory.load_memory", return_value=mock_memory):
        res = handler.match("super_key", mock_candidates)
        assert res is not None
        assert res.path == mock_candidates[2]


def test_alias_subquery_routing(sample_config: dict, mock_candidates: list[Path]):
    """AliasHandler parses compound queries and routes recursively."""
    handler = AliasHandler(sample_config)

    # Map "docs" config alias to mock Desktop/docs
    sample_config["aliases"]["docs_alias"] = ["docs"]

    # "latest pic on docs_alias" -> resolves docs_alias to docs, finds latest png -> pic2.png
    res = handler.match("latest pic on docs_alias", mock_candidates)
    assert res is not None
    assert res.path.name == "pic2.png"

    # "doc1 in docs_alias" -> resolves docs_alias to docs, finds doc1.pdf
    res = handler.match("doc1 in docs_alias", mock_candidates)
    assert res is not None
    assert res.path.name == "doc1.pdf"
