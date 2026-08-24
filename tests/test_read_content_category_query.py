"""Unit tests for content search (--read-content) when query matches a category keyword."""

from __future__ import annotations

from pathlib import Path

from sempath.engine import SearchEngine


def test_read_content_when_query_matches_category_keyword(sample_config: dict, tmp_path: Path):
    """Query 'yaml' with --read-content performs content scan on text files containing 'yaml'."""
    sample_config.setdefault("heuristics", {})["categories"] = {
        "code": {
            "keywords": ["yaml", "py", "js"],
            "extensions": ["yaml", "yml", "py", "js"],
        }
    }
    engine = SearchEngine(sample_config)

    # Create a config file and another file containing 'yaml' in its text
    f_config = tmp_path / "settings.txt"
    f_config.write_text("format: yaml\nversion: 1.0\n", encoding="utf-8")

    f_unrelated = tmp_path / "data.json"
    f_unrelated.write_text('{"key": "value"}', encoding="utf-8")

    res = engine.find_path("yaml", tmp_path, no_index=True, read_content=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path == f_config
    assert res.match.handler == "content_search"
    assert len(res.match.snippets) > 0
    assert "format: yaml" in res.match.snippets[0][1]
