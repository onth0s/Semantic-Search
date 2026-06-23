"""Unit tests for the SQLite-based IndexManager."""

from __future__ import annotations

from pathlib import Path

from sempath.index import IndexManager


def test_index_lifecycle(tmp_path: Path):
    # Setup directories
    root = tmp_path / "my_project"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    (root / "README.md").write_text("my documentation", encoding="utf-8")

    db_dir = tmp_path / "db_store"
    manager = IndexManager(db_dir)

    assert not manager.is_indexed(root)

    # Index root
    added, deleted = manager.create_or_update_index(root, depth=3)
    assert added > 0
    assert deleted == 0

    assert manager.is_indexed(root)
    assert manager.is_indexed(root / "src" / "main.py")

    # Get candidates
    candidates = manager.get_candidates(root)
    candidate_names = {p.name for p in candidates}
    assert "src" in candidate_names
    assert "main.py" in candidate_names
    assert "README.md" in candidate_names

    # Check root listing
    roots = manager.get_indexed_roots()
    assert str(root.resolve()) in roots

    # Incremental update (no changes)
    added, deleted = manager.create_or_update_index(root, depth=3)
    assert added == 0
    assert deleted == 0

    # Add a file and update index
    (root / "LICENSE").write_text("MIT", encoding="utf-8")
    added, deleted = manager.create_or_update_index(root, depth=3)
    assert added in (1, 2)
    assert deleted == 0

    candidates_new = manager.get_candidates(root)
    assert any(p.name == "LICENSE" for p in candidates_new)

    # Delete a root from index
    removed = manager.remove_root(root)
    assert removed is True
    assert not manager.is_indexed(root)
    assert len(manager.get_candidates(root)) == 0

    # Clear index
    manager.create_or_update_index(root, depth=3)
    assert manager.is_indexed(root)
    manager.clear_index()
    assert not manager.is_indexed(root)
