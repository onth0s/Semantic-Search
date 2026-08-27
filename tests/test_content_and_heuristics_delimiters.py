"""Unit tests for delimiter normalization in content search and wildcard category heuristics."""

from __future__ import annotations

from pathlib import Path

from sempath.engine import SearchEngine
from sempath.heuristics import extract_heuristics
from sempath.utils.file_ops import extract_matching_snippets


def test_blender_not_matched_as_backup_blend_extension(sample_config: dict):
    """Verify that queries with 'blender' do not falsely trigger category 'backup_blend'."""
    sample_config.setdefault("heuristics", {})["categories"] = {
        "backup_blend": {
            "keywords": ["blend1", "blend1s", "backup", "backups"],
            "extensions": ["blend*"],
        }
    }

    # Query with hyphen or space ending in 'Blender'
    h1 = extract_heuristics("Launching-Blender", sample_config)
    assert "backup_blend" not in h1.matched_categories
    assert h1.extensions is None or "blender" not in h1.extensions
    assert "launching" in h1.clean_query.lower()
    assert "blender" in h1.clean_query.lower()

    h2 = extract_heuristics("Launching Blender", sample_config)
    assert "backup_blend" not in h2.matched_categories
    assert h2.extensions is None or "blender" not in h2.extensions

    # Legitimate backup blend extension tokens or keywords
    h3 = extract_heuristics("model blend1", sample_config)
    assert "backup_blend" in h3.matched_categories
    assert h3.extensions == ["blend1"]

    h4 = extract_heuristics("model.blend2", sample_config)
    assert "backup_blend" in h4.matched_categories
    assert h4.extensions == ["blend2"]


def test_extract_matching_snippets_delimiters():
    """Verify snippet extraction handles hyphens, underscores, spaces, and case."""
    content = 'MsgBox("Hello")\nToolTip("Launching Blender...")\nExitApp\n'

    # Exact substring
    s1 = extract_matching_snippets(content, "Launching Blender")
    assert len(s1) == 1
    assert s1[0] == (2, 'ToolTip("Launching Blender...")')

    # Hyphenated query matching space-separated content
    s2 = extract_matching_snippets(content, "Launching-Blender")
    assert len(s2) == 1
    assert s2[0] == (2, 'ToolTip("Launching Blender...")')

    # Lowercase hyphenated query matching mixed-case content
    s3 = extract_matching_snippets(content, "launching-blender")
    assert len(s3) == 1
    assert s3[0] == (2, 'ToolTip("Launching Blender...")')

    # Underscore query matching space-separated content
    s4 = extract_matching_snippets(content, "launching_blender")
    assert len(s4) == 1
    assert s4[0] == (2, 'ToolTip("Launching Blender...")')


def test_engine_content_search_hyphenated_query(sample_config: dict, tmp_path: Path):
    """Verify SearchEngine find_path with read_content=True matches 'Launching-Blender'."""
    sample_config.setdefault("heuristics", {})["categories"] = {
        "backup_blend": {
            "keywords": ["blend1", "blend1s", "backup", "backups"],
            "extensions": ["blend*"],
        }
    }
    engine = SearchEngine(sample_config)

    ahk_file = tmp_path / "10_serial.ahk"
    ahk_file.write_text('ToolTip("Launching Blender...")\n', encoding="utf-8")

    res = engine.find_path("Launching-Blender", tmp_path, no_index=True, read_content=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path == ahk_file
    assert res.match.handler == "content_search"
    assert len(res.match.snippets) == 1
    assert 'ToolTip("Launching Blender...")' in res.match.snippets[0][1]
