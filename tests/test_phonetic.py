"""Unit tests for src.handlers.h5_phonetic — PhoneticMatchHandler."""

from pathlib import Path

import pytest

from src.handlers.h5_phonetic import PhoneticMatchHandler


@pytest.fixture
def mock_candidates() -> list[Path]:
    """Provide candidate paths for phonetic tests."""
    return [
        Path("C:/User/Desktop/docs/mane.txt"),
        Path("C:/User/Documents/their_file.txt"),
        Path("C:/User/Downloads/there_file.txt"),
    ]


def test_phonetic_homophones(sample_config: dict, mock_candidates: list[Path]):
    """Phonetic handler matches homophones correctly (e.g. main vs mane)."""
    handler = PhoneticMatchHandler(sample_config)

    # "main" matches "mane.txt" because they sound identical (metaphone: MN)
    res = handler.match("main", mock_candidates)
    assert res is not None
    assert res.path.name == "mane.txt"
    assert res.confidence == 0.75
    assert res.handler == "h5_phonetic"


def test_phonetic_homophones_phrase(sample_config: dict, mock_candidates: list[Path]):
    """Phonetic handler matches phonetically similar words in multi-word paths."""
    handler = PhoneticMatchHandler(sample_config)

    # "their_file" matches "their_file.txt" (exact/CI will catch it, but phonetic matches too)
    # Let's search for "there_file" - it should match "there_file.txt" but also "their_file.txt"
    # because they have identical phonetic codes.
    res = handler.match("there_file", mock_candidates)
    assert res is not None
    # Depending on tie-breaking/ordering, it should match one of them
    assert res.path.name in ("there_file.txt", "their_file.txt")
