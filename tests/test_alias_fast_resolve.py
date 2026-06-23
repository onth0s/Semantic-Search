"""Unit tests for the fast_resolve alias optimization in AliasHandler and SearchEngine."""

from pathlib import Path
from unittest.mock import patch

from src.engine import SearchEngine
from src.handlers.h6_alias import AliasHandler


def test_fast_resolve_learned_memory(sample_config: dict, tmp_path: Path):
    """fast_resolve correctly resolves from learned memory without scanning candidates."""
    handler = AliasHandler(sample_config)
    target_dir = tmp_path / "somewhere"
    target_dir.mkdir()

    mock_memory = [
        {
            "query": "quick_key",
            "path": str(target_dir),
            "timestamp": "2026-06-22T14:10:30Z",
            "hits": 1,
            "decay_rank": 1.0,
        }
    ]

    with patch("src.utils.memory.load_memory", return_value=mock_memory):
        res = handler.fast_resolve("quick_key", tmp_path)
        assert res == target_dir


def test_fast_resolve_config_alias_bfs(sample_config: dict, tmp_path: Path):
    """fast_resolve resolves config alias via BFS up to depth 5."""
    handler = AliasHandler(sample_config)

    # config aliases has: "main": ["__MAIN", "principal", "important", "primary", "master"]
    # Let's create primary under a subdirectory (depth 2)
    depth1 = tmp_path / "subdir1"
    depth1.mkdir()
    target_dir = depth1 / "primary"
    target_dir.mkdir()

    res = handler.fast_resolve("main", tmp_path)
    assert res == target_dir

    res_target = handler.fast_resolve("principal", tmp_path)
    assert res_target == target_dir


def test_engine_early_bypass_direct(sample_config: dict, tmp_path: Path):
    """SearchEngine.find_path bypasses candidate gathering for direct alias queries."""
    engine = SearchEngine(sample_config)

    depth1 = tmp_path / "subdir1"
    depth1.mkdir()
    target_dir = depth1 / "primary"
    target_dir.mkdir()

    # If it bypasses candidate gathering, it shouldn't access the index manager's is_indexed or get_candidates.
    # We patch them to raise an assertion error if called.
    with (
        patch.object(
            engine.index_manager,
            "is_indexed",
            side_effect=AssertionError("is_indexed should not be called"),
        ),
        patch(
            "src.engine.scan_directory",
            side_effect=AssertionError("scan_directory should not be called"),
        ),
    ):
        res = engine.find_path("principal", tmp_path)
        assert res.status == "success"
        assert res.match.path == target_dir
        assert res.match.handler == "h6_alias"


def test_engine_early_bypass_routing(sample_config: dict, tmp_path: Path):
    """SearchEngine.find_path updates search_root and limits search scope for routing alias queries."""
    engine = SearchEngine(sample_config)

    # Let's create a main alias directory and a file under it
    main_dir = tmp_path / "__MAIN"
    main_dir.mkdir()
    target_file = main_dir / "report.pdf"
    target_file.write_text("content", encoding="utf-8")

    # When query is "report on main", engine should fast-resolve "main" to "__MAIN"
    # and set search_root to "__MAIN".
    # We mock is_indexed to verify it is called with resolved "__MAIN", not tmp_path.
    original_is_indexed = engine.index_manager.is_indexed
    called_roots = []

    def mock_is_indexed(root_path):
        called_roots.append(root_path)
        return original_is_indexed(root_path)

    with patch.object(engine.index_manager, "is_indexed", side_effect=mock_is_indexed):
        res = engine.find_path("report on main", tmp_path)
        assert res.status == "success"
        assert res.match.path == target_file
        assert main_dir in called_roots
        assert tmp_path not in called_roots
