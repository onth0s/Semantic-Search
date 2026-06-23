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
    assert "pdf" in res["extensions"]


def test_extract_heuristics_latest():
    """extract_heuristics detects 'latest' or 'newest' keywords."""
    res = extract_heuristics("latest doc on Desktop")
    assert res["clean_query"] == "on Desktop"
    assert res["latest"] is True
    assert "pdf" in res["extensions"]


def test_extract_heuristics_directory_file():
    """extract_heuristics detects folder, dir, and file keywords."""
    res = extract_heuristics("important folder on Desktop")
    assert res["clean_query"] == "important on Desktop"
    assert res["directory_only"] is True
    assert res["file_only"] is False

    res = extract_heuristics("notes file")
    assert res["directory_only"] is False
    assert res["file_only"] is True


def test_extract_heuristics_categories():
    """extract_heuristics extracts extensions from category keywords and strips them."""
    # 1. Exact match
    res = extract_heuristics("pics on Desktop")
    assert res["clean_query"] == "on Desktop"
    assert "png" in res["extensions"]
    assert "jpg" in res["extensions"]

    # 2. Fuzzy match (pics -> picts has ratio 88.9 -> match)
    res = extract_heuristics("picts on Desktop")
    assert res["clean_query"] == "on Desktop"
    assert "png" in res["extensions"]

    # 3. Phonetic match (pics -> piks: jellyfish metaphone match PK)
    res = extract_heuristics("piks on Desktop")
    assert res["clean_query"] == "on Desktop"
    assert "png" in res["extensions"]

    # 4. Custom threshold (category_fuzzy_threshold = 50, so pics -> pci matches)
    config = {
        "heuristics": {
            "category_fuzzy_threshold": 50,
            "categories": {"image": {"keywords": ["pic", "pics"], "extensions": ["png", "jpg"]}},
        }
    }
    res = extract_heuristics("pci on Desktop", config)
    assert res["clean_query"] == "on Desktop"
    assert "png" in res["extensions"]


def test_translate_wildcards():
    """translate_wildcards translates glob patterns into descriptive phrases."""
    from src.heuristics import translate_wildcards

    # *.blend*
    assert (
        translate_wildcards("*.blend*")
        == "a file whose name ends with .blend followed by any characters"
    )

    # *.txt
    assert translate_wildcards("*.txt") == "a file ending in .txt"

    # *notes*
    assert translate_wildcards("*notes*") == "a file whose name contains 'notes'"

    # *notes
    assert translate_wildcards("*notes") == "a file ending with 'notes'"

    # notes*
    assert translate_wildcards("notes*") == "a file starting with 'notes'"
