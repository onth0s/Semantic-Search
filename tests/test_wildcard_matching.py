"""Tests for wildcard/glob query matching and destructuring across handlers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sempath.engine import SearchEngine
from sempath.handlers.h1_exact import ExactMatchHandler
from sempath.handlers.h2_case_insensitive import CaseInsensitiveHandler
from sempath.handlers.h3_token_normalized import TokenNormalizedHandler
from sempath.handlers.h4_fuzzy import FuzzyMatchHandler
from sempath.handlers.h5_phonetic import PhoneticMatchHandler
from sempath.handlers.h6_alias import AliasHandler


@pytest.fixture
def mock_candidates() -> list[Path]:
    return [
        Path("C:/User/Desktop/notes.txt"),
        Path("C:/User/Desktop/MyProject"),
        Path("C:/User/Desktop/my_project"),
        Path("C:/User/Desktop/archive.zip"),
        Path("C:/User/Desktop/backup.blend1"),
        Path("C:/User/Desktop/backup.blend2"),
    ]


def test_h1_exact_wildcard(sample_config: dict, mock_candidates: list[Path]):
    handler = ExactMatchHandler(sample_config)
    # Case-sensitive glob matching
    res = handler.match("*.txt", mock_candidates)
    assert res is not None
    assert res.path.name == "notes.txt"

    res = handler.match("*.TXT", mock_candidates)
    assert res is None  # Case-sensitive!


def test_h2_case_insensitive_wildcard(sample_config: dict, mock_candidates: list[Path]):
    handler = CaseInsensitiveHandler(sample_config)
    # Case-insensitive glob matching
    res = handler.match("*.TXT", mock_candidates)
    assert res is not None
    assert res.path.name == "notes.txt"


def test_h3_token_normalized_wildcard(sample_config: dict, mock_candidates: list[Path]):
    handler = TokenNormalizedHandler(sample_config)
    # Token-normalized glob matching (unordered token sets)
    res = handler.match("my_* project", mock_candidates)
    assert res is not None
    assert res.path.name in ("MyProject", "my_project")


def test_h4_fuzzy_destructuring(sample_config: dict, mock_candidates: list[Path]):
    handler = FuzzyMatchHandler(sample_config)
    # Fuzzy matching by stripping wildcards
    # my_pr*ect -> my_prect fuzzy matches my_project
    res = handler.match("my_pr*ect", mock_candidates)
    assert res is not None
    assert res.path.name == "my_project"


def test_h5_phonetic_destructuring(sample_config: dict, mock_candidates: list[Path]):
    handler = PhoneticMatchHandler(sample_config)
    # Phonetic matching by stripping wildcards
    # my_pr*jct -> my_prjct metaphone matches my_project
    res = handler.match("my_pr*jct", mock_candidates)
    assert res is not None
    assert res.path.name == "my_project"


def test_h6_alias_wildcard(sample_config: dict, mock_candidates: list[Path]):
    # Setup alias config with wildcard query/target
    cfg = dict(sample_config)
    cfg["aliases"] = {"docs*": ["notes*"]}
    handler = AliasHandler(cfg)
    # notes.txt is under candidates
    res = handler.match("docs", mock_candidates)
    assert res is not None
    assert res.path.name == "notes.txt"


def test_engine_wildcard_extensions(tmp_path: Path, sample_config: dict):
    # Create temp files
    f1 = tmp_path / "backup.blend1"
    f2 = tmp_path / "backup.blend2"
    f3 = tmp_path / "backup.txt"
    f1.write_text("b1", encoding="utf-8")
    f2.write_text("b2", encoding="utf-8")
    f3.write_text("txt", encoding="utf-8")

    # Configure categories with wildcard extension
    cfg = dict(sample_config)
    cfg["heuristics"] = {
        "categories": {"backup_blend": {"keywords": ["blend1"], "extensions": ["blend*"]}}
    }
    engine = SearchEngine(cfg)

    # Search for "blend1" which is a category keyword for backup_blend.
    res = engine.find_path("blend1", tmp_path, no_index=True, min_confidence=0.1)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path in (f1, f2)


def test_verbose_logging(tmp_path: Path, sample_config: dict):
    # Create a temp file
    f1 = tmp_path / "my_project"
    f1.write_text("content", encoding="utf-8")

    engine = SearchEngine(sample_config)

    # Set up Click Context with verbose=True
    ctx = MagicMock()
    ctx.obj = {"verbose": True}

    with (
        patch("click.get_current_context", return_value=ctx),
        patch("sempath.utils.console.err_console.print") as mock_print,
    ):
        res = engine.find_path("my_project", tmp_path, no_index=True, min_confidence=0.1)
        assert res.status == "success"

        # Verify that err_console.print was called with diagnostic logs
        assert mock_print.called
        printed_args = []
        for call in mock_print.call_args_list:
            if call[0]:
                printed_args.append(call[0][0])
        assert any("Gathered" in arg for arg in printed_args)
        assert any("Heuristics extracted" in arg for arg in printed_args)


def test_category_keyword_file_match(tmp_path: Path, sample_config: dict):
    # Tests that query "script md" matches SCRIPT.md
    f1 = tmp_path / "SCRIPT.md"
    f1.write_text("script content", encoding="utf-8")
    f2 = tmp_path / "other.md"
    f2.write_text("other content", encoding="utf-8")

    engine = SearchEngine(sample_config)
    res = engine.find_path("script md", tmp_path, no_index=True, min_confidence=0.1)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path.name == "SCRIPT.md"


def test_dot_separated_category_keyword_file_match(tmp_path: Path, sample_config: dict):
    # Tests that query "script.md" matches SCRIPT.md instead of being stripped to "."
    f1 = tmp_path / "SCRIPT.md"
    f1.write_text("script content", encoding="utf-8")
    f2 = tmp_path / "other.md"
    f2.write_text("other content", encoding="utf-8")

    engine = SearchEngine(sample_config)
    res = engine.find_path("script.md", tmp_path, no_index=True, min_confidence=0.1)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path.name == "SCRIPT.md"


def test_single_category_keyword_file_match(tmp_path: Path, sample_config: dict):
    # Tests that query "script" matches SCRIPT.md even though "script" is a
    # keyword for category "code" and SCRIPT.md is a document (not a code file)
    f1 = tmp_path / "SCRIPT.md"
    f1.write_text("script content", encoding="utf-8")
    f2 = tmp_path / "other.py"
    f2.write_text("py code", encoding="utf-8")

    engine = SearchEngine(sample_config)
    res = engine.find_path("script", tmp_path, no_index=True, min_confidence=0.1)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path.name == "SCRIPT.md"
