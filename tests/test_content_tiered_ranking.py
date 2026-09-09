"""Tests for tiered confidence content searching and snippet highlighting."""

from pathlib import Path

from sempath.cli.formatting import _format_snippet
from sempath.constants import (
    CONTENT_TIER_CI_SUBSTRING,
    CONTENT_TIER_CI_TOKEN,
    CONTENT_TIER_EXACT_TOKEN,
)
from sempath.engine import SearchEngine
from sempath.utils.file_ops import (
    TIER_CI_SUBSTRING,
    TIER_CI_TOKEN,
    TIER_DELIMITED,
    TIER_EXACT_SUBSTRING,
    TIER_EXACT_TOKEN,
    extract_content_match_info,
    extract_matching_snippets,
)


def test_extract_content_match_info_tiers():
    # Tier 1: exact token bounded match
    t1 = extract_content_match_info("Process Execution System (PES) is active.", "PES")
    assert t1 is not None
    assert t1.best_tier == TIER_EXACT_TOKEN
    assert t1.total_occurrences == 1
    assert len(t1.snippets) == 1

    # Tier 1 with multiple occurrences
    t1_multi = extract_content_match_info("PES-STATE: PES is running. (PES)", "PES")
    assert t1_multi is not None
    assert t1_multi.best_tier == TIER_EXACT_TOKEN
    assert t1_multi.total_occurrences == 3

    # Tier 2: case-insensitive token match
    t2 = extract_content_match_info("pes-validate script is ready.", "PES")
    assert t2 is not None
    assert t2.best_tier == TIER_CI_TOKEN
    assert t2.total_occurrences == 1

    # Tier 3: exact substring inside another word
    t3 = extract_content_match_info("FOOPESBAR is an identifier.", "PES")
    assert t3 is not None
    assert t3.best_tier == TIER_EXACT_SUBSTRING
    assert t3.total_occurrences == 1

    # Tier 4: case-insensitive substring inside another word (like foreign-types)
    t4 = extract_content_match_info('name = "foreign-types"\nversion = "0.3.2"', "PES")
    assert t4 is not None
    assert t4.best_tier == TIER_CI_SUBSTRING
    assert t4.total_occurrences == 1

    # Tier 5: delimiter-separated query
    t5 = extract_content_match_info("Launching Blender version 4.2", "Launching-Blender")
    assert t5 is not None
    assert t5.best_tier == TIER_DELIMITED


def test_backward_compatibility_extract_matching_snippets():
    content = "Hello World\nAnother PES line\nThird line"
    snippets = extract_matching_snippets(content, "PES")
    assert len(snippets) == 1
    assert snippets[0] == (2, "Another PES line")


def test_content_search_tiered_ranking_order(sample_config: dict, tmp_path: Path):
    """Verify that exact tokens rank above case-insensitive, which rank above substrings."""
    # File 1: Exact token definitions (DAEMON.md)
    f_daemon = tmp_path / "DAEMON.md"
    f_daemon.write_text(
        "Process Execution System (PES)\nPES-STATE\nPES daemon lifecycle\n",
        encoding="utf-8",
    )

    # File 2: Single exact token mention (AGENTS.md)
    f_agents = tmp_path / "AGENTS.md"
    f_agents.write_text("Refer to (PES) protocol.\n", encoding="utf-8")

    # File 3: Case-insensitive token (test_pes.py)
    f_code = tmp_path / "test_pes.py"
    f_code.write_text("def test_pes_state(): pass\n", encoding="utf-8")

    # File 4: Mid-word substring match (Cargo.lock)
    f_cargo = tmp_path / "Cargo.lock"
    f_cargo.write_text(
        '[[package]]\nname = "foreign-types"\nversion = "0.3.2"\n'
        '[[package]]\nname = "rustls-pki-types"\nversion = "1.0"\n',
        encoding="utf-8",
    )

    engine = SearchEngine(sample_config)
    result = engine.find_path("PES", tmp_path, no_index=True, read_content=True, top_n=10)

    assert result.status == "success"
    all_matches = ([result.match] if result.match else []) + result.near_misses
    assert len(all_matches) == 4

    matched_names = [m.path.name for m in all_matches]
    # DAEMON.md should be #1 (Tier 1 + 3 occurrences)
    assert matched_names[0] == "DAEMON.md"
    assert all_matches[0].confidence >= CONTENT_TIER_EXACT_TOKEN

    # AGENTS.md should be #2 (Tier 1 + 1 occurrence)
    assert matched_names[1] == "AGENTS.md"
    assert all_matches[1].confidence >= CONTENT_TIER_EXACT_TOKEN
    assert all_matches[0].confidence > all_matches[1].confidence

    # test_pes.py should be #3 (Tier 2)
    assert matched_names[2] == "test_pes.py"
    assert CONTENT_TIER_CI_TOKEN <= all_matches[2].confidence < CONTENT_TIER_EXACT_TOKEN

    # Cargo.lock MUST still be matched (not dropped), but ranked last (Tier 4)
    assert matched_names[3] == "Cargo.lock"
    assert CONTENT_TIER_CI_SUBSTRING <= all_matches[3].confidence < CONTENT_TIER_CI_TOKEN


def test_snippet_highlighting():
    # Exact case highlight
    snip1 = _format_snippet("Process Execution System (PES) active", "PES")
    assert "[bold yellow]PES[/]" in snip1

    # Case-insensitive highlight
    snip2 = _format_snippet('name = "foreign-types"', "PES")
    assert "[bold yellow]pes[/]" in snip2
    assert "foreign-ty[bold yellow]pes[/]" in snip2

    # Preserves mixed casing
    snip3 = _format_snippet("Pes and pEs and PES", "pes")
    assert "[bold yellow]Pes[/]" in snip3
    assert "[bold yellow]pEs[/]" in snip3
    assert "[bold yellow]PES[/]" in snip3
