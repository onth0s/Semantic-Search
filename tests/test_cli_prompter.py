"""Unit tests for sempath.cli.prompter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import click
import pytest

from sempath.cli.prompter import prompt_disambiguation_selection
from sempath.models import MatchResult


def test_prompt_disambiguation_selection_valid(tmp_path: Path):
    path1 = tmp_path / "item1.txt"
    path2 = tmp_path / "item2.txt"
    path1.write_text("1")
    path2.write_text("2")

    matches = [
        MatchResult(path=path1, confidence=0.85, handler="h4_fuzzy"),
        MatchResult(path=path2, confidence=0.75, handler="h5_phonetic"),
    ]

    with patch("click.prompt", return_value=1):
        chosen = prompt_disambiguation_selection(matches, verbose=True)
        assert chosen == matches[0]

    with patch("click.prompt", return_value=2):
        chosen = prompt_disambiguation_selection(matches, verbose=False)
        assert chosen == matches[1]


def test_prompt_disambiguation_selection_none_of_above(tmp_path: Path):
    path1 = tmp_path / "item1.txt"
    path1.write_text("1")
    matches = [MatchResult(path=path1, confidence=0.85, handler="h4_fuzzy")]

    # Option 2 is "None of the above"
    with patch("click.prompt", return_value=2):
        chosen = prompt_disambiguation_selection(matches)
        assert chosen is None


def test_prompt_disambiguation_abort(tmp_path: Path):
    path1 = tmp_path / "item1.txt"
    path1.write_text("1")
    matches = [MatchResult(path=path1, confidence=0.85, handler="h4_fuzzy")]

    with patch("click.prompt", side_effect=click.Abort), pytest.raises(click.Abort):
        prompt_disambiguation_selection(matches)
