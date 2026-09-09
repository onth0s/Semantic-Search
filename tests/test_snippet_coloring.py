"""Tests for tiered snippet highlight coloring in _format_snippet."""

from __future__ import annotations

from sempath.cli.formatting import _format_snippet, _tier_color_for_occurrence


class TestTierColorForOccurrence:
    """Unit tests for the per-occurrence tier color helper."""

    def test_tier1_exact_token_at_boundary(self) -> None:
        line = "(PES)"
        color = _tier_color_for_occurrence("PES", "PES", line, 1, 4, False)
        assert color == "bold green"

    def test_tier1_exact_token_standalone(self) -> None:
        line = "PES-STATE"
        color = _tier_color_for_occurrence("PES", "PES", line, 0, 3, False)
        assert color == "bold green"

    def test_tier2_ci_token_boundary(self) -> None:
        line = "pes-validate"
        color = _tier_color_for_occurrence("pes", "PES", line, 0, 3, False)
        assert color == "bold cyan"

    def test_tier3_exact_substring_no_boundary(self) -> None:
        line = "FOOPESBAR"
        color = _tier_color_for_occurrence("PES", "PES", line, 3, 6, False)
        assert color == "bold yellow"

    def test_tier4_ci_substring_no_boundary(self) -> None:
        line3 = "typesafe"
        idx = line3.lower().find("pes")
        assert idx != -1
        color = _tier_color_for_occurrence("pes", "PES", line3, idx, idx + 3, False)
        assert color == "yellow"

    def test_tier5_delimiter_match(self) -> None:
        line = "Launching-Blender"
        color = _tier_color_for_occurrence(
            "Launching-Blender", "Launching Blender", line, 0, 17, True
        )
        assert color == "bold cyan"


class TestFormatSnippet:
    """Integration tests verifying the Rich markup output of _format_snippet."""

    def test_no_query_returns_escaped(self) -> None:
        assert _format_snippet("hello world") == "hello world"
        assert _format_snippet("hello world", "") == "hello world"
        assert _format_snippet("hello world", ".") == "hello world"

    def test_tier1_exact_token_green(self) -> None:
        result = _format_snippet("Initializes PES-STATE and commits", "PES")
        assert "[bold green]PES[/]" in result

    def test_tier1_exact_token_in_parens(self) -> None:
        result = _format_snippet("Architecture: AVO + PES", "PES")
        assert "[bold green]PES[/]" in result

    def test_tier2_ci_token_cyan(self) -> None:
        result = _format_snippet("running pes-validate binary", "PES")
        assert "[bold cyan]pes[/]" in result

    def test_tier3_exact_substring_yellow(self) -> None:
        result = _format_snippet("token FOOPESBAR found", "PES")
        assert "[bold yellow]PES[/]" in result

    def test_tier4_ci_substring_dim_yellow(self) -> None:
        result = _format_snippet("the types module", "PES")
        assert "[yellow]pes[/]" in result
        assert "[bold yellow]pes[/]" not in result
        assert "[bold green]pes[/]" not in result

    def test_tier5_delimiter_normalized_cyan(self) -> None:
        result = _format_snippet("step Launching-Blender complete", "Launching Blender")
        assert "[bold cyan]Launching-Blender[/]" in result

    def test_mixed_tiers_same_line(self) -> None:
        result = _format_snippet("PES is in types PES-tools", "PES")
        assert "[bold green]PES[/]" in result

    def test_no_match_returns_plain(self) -> None:
        result = _format_snippet("completely unrelated line", "PES")
        assert result == "completely unrelated line"
