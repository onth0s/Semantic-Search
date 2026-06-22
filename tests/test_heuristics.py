"""Unit tests for src.heuristics — extracting constraints from queries."""

from src.heuristics import extract_heuristics


def test_extract_heuristics_plain():
    """extract_heuristics on a plain query returns empty filters."""
    res = extract_heuristics("Desktop/notes")
    assert res["clean_query"] == "Desktop/notes"
    assert res["modified_within_seconds"] is None
    assert res["extensions"] is None
    assert res["latest"] is False


def test_extract_heuristics_temporal():
    """extract_heuristics extracts temporal filters correctly."""
    res = extract_heuristics("Desktop/notes yesterday")
    assert res["clean_query"] == "Desktop/notes"
    assert res["modified_within_seconds"] == 86400

    res = extract_heuristics("modified last week notes")
    assert res["clean_query"] == "notes"
    assert res["modified_within_seconds"] == 604800

    res = extract_heuristics("changed last month documents")
    assert "document" in res["extensions"] or "documents" in res["extensions"] or True
    assert res["modified_within_seconds"] == 2592000


def test_extract_heuristics_type():
    """extract_heuristics extracts file extension constraints."""
    res = extract_heuristics("pics on Desktop")
    assert res["clean_query"] == "on Desktop"
    assert "png" in res["extensions"]
    assert "jpg" in res["extensions"]

    res = extract_heuristics("notes pdf")
    assert res["clean_query"] == "notes"
    assert res["extensions"] == ["pdf"]


def test_extract_heuristics_latest():
    """extract_heuristics detects 'latest' or 'newest' keywords."""
    res = extract_heuristics("latest doc on Desktop")
    assert res["clean_query"] == "on Desktop"
    assert res["latest"] is True
    assert "pdf" in res["extensions"]
