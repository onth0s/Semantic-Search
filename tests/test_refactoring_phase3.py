from pathlib import Path

from sempath.config import load_config, save_config
from sempath.engine import SearchEngine
from sempath.models import MatchResult


def test_t1_read_content_logic(tmp_path: Path, sample_config: dict):
    """Verify that read_content=True scans text files and returns correct matches."""
    f = tmp_path / "dummy_doc.txt"
    f.write_text("UniqueKeywordForContentSearchHere", encoding="utf-8")

    engine = SearchEngine(sample_config)
    res = engine.find_path(
        query="UniqueKeywordForContentSearchHere",
        root_dir=tmp_path,
        no_index=True,
        read_content=True,
        min_confidence=0.1,
    )
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path == f
    assert res.match.handler == "content_search"


def test_t3_save_config_logic(tmp_path: Path):
    """Verify that save_config writes to disk and deep-merges keys correctly."""
    cfg_file = tmp_path / "test_config.yaml"
    initial_cfg = {"verbose": False, "handlers": {"h4_threshold": 60}}
    save_config(initial_cfg, path=cfg_file)

    # Load and verify initial write
    loaded = load_config(cfg_file)
    assert loaded["verbose"] is False
    assert loaded["handlers"]["h4_threshold"] == 60

    # Save update (deep merge verification)
    updates = {"verbose": True, "handlers": {"h7_model": "custom-model"}}
    save_config(updates, path=cfg_file)

    loaded_updated = load_config(cfg_file)
    assert loaded_updated["verbose"] is True
    # Verify h4_threshold from initial write is preserved (deep merge)
    assert loaded_updated["handlers"]["h4_threshold"] == 60
    assert loaded_updated["handlers"]["h7_model"] == "custom-model"


def test_t4_sqlite_index_edge_cases(tmp_path: Path, sample_config: dict):
    """Verify IndexManager behavior with empty directory and auto-creation."""
    engine = SearchEngine(sample_config)
    # 1. Non-existent path returns empty candidates
    non_existent = tmp_path / "non_existent_folder"
    cands = engine._gather_candidates(non_existent, depth=5, use_index=True, exclude_patterns=[])
    assert cands == []

    # 2. Empty directory returns empty candidates list but creates index cleanly
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    cands_empty = engine._gather_candidates(empty_dir, depth=5, use_index=True, exclude_patterns=[])
    assert cands_empty == []
    assert engine.index_manager.is_indexed(empty_dir)


def test_t6_sort_strategy_combinations(tmp_path: Path, sample_config: dict):
    """Verify that engine correctly routes and sorts by size/mtime flags."""
    # Create 3 files of varying sizes and mtimes
    import time

    f_small_old = tmp_path / "small_old.txt"
    f_small_old.write_text("a", encoding="utf-8")  # 1 byte
    time.sleep(0.01)

    f_large_mid = tmp_path / "large_mid.txt"
    f_large_mid.write_text("abcde", encoding="utf-8")  # 5 bytes
    time.sleep(0.01)

    f_medium_new = tmp_path / "medium_new.txt"
    f_medium_new.write_text("abc", encoding="utf-8")  # 3 bytes

    # Initialize confident matches list
    m_small = MatchResult(f_small_old, 0.9, "h1_exact")
    m_large = MatchResult(f_large_mid, 0.9, "h1_exact")
    m_medium = MatchResult(f_medium_new, 0.9, "h1_exact")

    engine = SearchEngine(sample_config)

    # Test Sort Strategy: latest
    matches = [m_small, m_large, m_medium]
    engine._sort_confident_matches(
        matches,
        latest_final=True,
        largest_final=False,
        smallest_final=False,
        oldest_final=False,
    )
    assert matches[0].path == f_medium_new

    # Test Sort Strategy: largest
    matches = [m_small, m_large, m_medium]
    engine._sort_confident_matches(
        matches,
        latest_final=False,
        largest_final=True,
        smallest_final=False,
        oldest_final=False,
    )
    assert matches[0].path == f_large_mid

    # Test Sort Strategy: smallest
    matches = [m_small, m_large, m_medium]
    engine._sort_confident_matches(
        matches,
        latest_final=False,
        largest_final=False,
        smallest_final=True,
        oldest_final=False,
    )
    assert matches[0].path == f_small_old

    # Test Sort Strategy: oldest
    matches = [m_small, m_large, m_medium]
    engine._sort_confident_matches(
        matches,
        latest_final=False,
        largest_final=False,
        smallest_final=False,
        oldest_final=True,
    )
    assert matches[0].path == f_small_old


def test_t8_gitignore_toggling(tmp_path: Path, sample_config: dict):
    """Verify find_path toggling of respect_gitignore parameter."""
    # Create gitignored structure
    git_dir = tmp_path
    gitignore = git_dir / ".gitignore"
    gitignore.write_text("ignored_file.txt", encoding="utf-8")

    ignored_file = git_dir / "ignored_file.txt"
    ignored_file.write_text("hello", encoding="utf-8")

    engine = SearchEngine(sample_config)

    # 1. By default, respect_gitignore=True, so ignored_file.txt is NOT matched
    res_respect = engine.find_path(
        query="ignored_file.txt",
        root_dir=tmp_path,
        no_index=True,
        respect_gitignore=True,
        min_confidence=0.1,
    )
    assert res_respect.status != "success"

    # 2. When respect_gitignore=False, ignored_file.txt IS matched successfully
    res_no_respect = engine.find_path(
        query="ignored_file.txt",
        root_dir=tmp_path,
        no_index=True,
        respect_gitignore=False,
        min_confidence=0.1,
    )
    assert res_no_respect.status == "success"
    assert res_no_respect.match is not None
    assert res_no_respect.match.path == ignored_file
