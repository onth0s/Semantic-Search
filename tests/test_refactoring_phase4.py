import sqlite3
from pathlib import Path

from sempath import MatchResult, SearchEngine, SearchResult
from sempath.index import IndexManager


def test_t9_package_level_exposures():
    """Verify that key classes are exposed at package level."""
    assert SearchEngine is not None
    assert SearchResult is not None
    assert MatchResult is not None


def test_t10_sqlite_connection_context_closure(tmp_path: Path):
    """Verify that IndexManager database connections are closed and transaction is committed."""
    index = IndexManager(tmp_path)
    # Perform some index operation
    index.clear_index()

    # The database file exists
    db_file = tmp_path / "index.db"
    assert db_file.exists()

    # Attempt to connect externally and check connection behaves
    conn = sqlite3.connect(db_file)
    try:
        row = conn.execute("SELECT COUNT(*) FROM paths").fetchone()
        assert row[0] == 0
    finally:
        conn.close()


def test_t11_schema_validation_and_recreation(tmp_path: Path):
    """Verify that database detects schema changes and recreates tables."""
    db_dir = tmp_path / "subdir"
    db_dir.mkdir()
    db_file = db_dir / "index.db"

    # 1. Create a dummy invalid database file with missing columns in paths table
    conn = sqlite3.connect(db_file)
    with conn:
        conn.execute("CREATE TABLE paths (id INTEGER PRIMARY KEY, path TEXT)")
        conn.execute("CREATE TABLE indexed_roots (path TEXT PRIMARY KEY, indexed_at REAL)")
    conn.close()

    # 2. Instantiate IndexManager pointing to this DB - it should detect mismatch and recreate
    index = IndexManager(db_dir)
    assert index is not None

    # 3. Check that the paths table now has all expected columns
    conn = sqlite3.connect(db_file)
    try:
        cursor = conn.execute("PRAGMA table_info(paths)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {
            "id",
            "path",
            "basename",
            "parent_dir",
            "mtime",
            "size",
            "is_dir",
            "tokens",
            "phonetic",
        }
        assert expected.issubset(columns)
    finally:
        conn.close()


def test_t12_index_needs_update_optimization(tmp_path: Path):
    """Verify check_index_needs_update logic detecting physical count mismatches."""
    index = IndexManager(tmp_path)

    # Create dummy files
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("a", encoding="utf-8")
    f2.write_text("b", encoding="utf-8")

    # Initially, it is not indexed, check_index_needs_update should indicate it's out of sync
    assert index.check_index_needs_update(tmp_path) is True

    # Index it
    index.create_or_update_index(tmp_path)

    # Now count should match
    assert index.check_index_needs_update(tmp_path) is False

    # Delete a file physically
    f1.unlink()

    # Should detect mismatch again
    assert index.check_index_needs_update(tmp_path) is True
