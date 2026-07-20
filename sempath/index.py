"""SQLite-based persistent path index manager for sempath.

Allows creating, updating, listing, and removing indexed directories and files.
Stores paths, basenames, tokenized names, phonetic codes, and metadata (mtime, size)
to avoid expensive disk walks on future invocations.
"""

from __future__ import annotations

import os
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path

import jellyfish

from sempath.scanner import scan_directory
from sempath.utils.tokenize import normalize_tokens


class IndexManager:
    """Manages the SQLite database index for paths."""

    def __init__(self, db_dir: Path) -> None:
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "index.db"
        self._init_db()

    @contextmanager
    def _connection(self):
        """Context manager to yield a connection.

        Ensures WAL mode, busy timeout, transaction handling, and auto-closure.
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
        except sqlite3.OperationalError:
            pass
        try:
            with closing(conn), conn:
                yield conn
        except sqlite3.OperationalError as e:
            raise e

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._connection() as conn:
            self._check_and_create_schema(conn)

    def _check_and_create_schema(self, conn: sqlite3.Connection) -> None:
        """Check if schema is valid, and recreate tables if invalid or outdated."""
        schema_valid = True
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('paths', 'indexed_roots')"
            ).fetchall()
            if len(tables) < 2:
                schema_valid = False
            else:
                cursor = conn.execute("PRAGMA table_info(paths)")
                columns = {row["name"] for row in cursor.fetchall()}
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
                if not expected.issubset(columns):
                    schema_valid = False
        except Exception:
            schema_valid = False

        if not schema_valid:
            conn.execute("DROP TABLE IF EXISTS paths")
            conn.execute("DROP TABLE IF EXISTS indexed_roots")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS indexed_roots (
                path TEXT PRIMARY KEY,
                indexed_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paths (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                basename TEXT NOT NULL,
                parent_dir TEXT NOT NULL,
                mtime REAL NOT NULL,
                size INTEGER NOT NULL,
                is_dir INTEGER NOT NULL,
                tokens TEXT NOT NULL,
                phonetic TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_paths_parent ON paths (parent_dir)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_paths_path ON paths (path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_paths_basename ON paths (basename)")

    def _compute_phonetic_codes(self, text: str) -> str:
        """Compute space-separated Metaphone codes for alphanumeric tokens."""
        codes = []
        for token in normalize_tokens(text):
            if token.isalpha():
                try:
                    code = jellyfish.metaphone(token)
                    if code:
                        codes.append(code)
                except Exception:
                    pass
            else:
                codes.append(token)
        return " ".join(codes)

    def is_indexed(self, root_path: Path) -> bool:
        """Check if root_path or any of its ancestors are already indexed."""
        resolved_root = Path(root_path).resolve()
        resolved_str = str(resolved_root)
        with self._connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM indexed_roots WHERE path = ?", (resolved_str,)
            ).fetchone()
            if row:
                return True

            roots = conn.execute("SELECT path FROM indexed_roots").fetchall()
            for r in roots:
                r_path = Path(r["path"])
                if resolved_root.is_relative_to(r_path):
                    return True
        return False

    def get_indexed_roots(self) -> list[str]:
        """Return a list of all indexed root directories."""
        with self._connection() as conn:
            rows = conn.execute("SELECT path FROM indexed_roots ORDER BY path").fetchall()
            return [row["path"] for row in rows]

    def clear_index(self) -> None:
        """Clear all paths and roots from the database."""
        with self._connection() as conn:
            conn.execute("DELETE FROM paths")
            conn.execute("DELETE FROM indexed_roots")

    def remove_root(self, root_path: Path) -> bool:
        """Remove a root directory and all its descendants from the index."""
        resolved_root = Path(root_path).resolve()
        resolved_str = str(resolved_root)
        prefix = resolved_str if resolved_str.endswith(os.sep) else resolved_str + os.sep
        with self._connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM indexed_roots WHERE path = ?", (resolved_str,)
            ).fetchone()
            if not row:
                return False

            conn.execute("DELETE FROM indexed_roots WHERE path = ?", (resolved_str,))
            conn.execute(
                "DELETE FROM paths WHERE path = ? OR SUBSTR(path, 1, ?) = ?",
                (resolved_str, len(prefix), prefix),
            )
            return True

    def _count_physical_files(self, root_path: Path) -> int:
        """Count physical files and directories recursively in a fast manner."""
        count = 1  # Include the root directory itself
        try:
            for _, dirs, files in os.walk(root_path):
                count += len(dirs) + len(files)
        except Exception:
            pass
        return count

    def check_index_needs_update(self, root_path: Path) -> bool:
        """Compare database count against physical files/dirs count to see if update is needed."""
        resolved_root = Path(root_path).resolve()
        if not resolved_root.exists():
            return True

        resolved_str = str(resolved_root)
        prefix = resolved_str if resolved_str.endswith(os.sep) else resolved_str + os.sep

        with self._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM paths WHERE path = ? OR SUBSTR(path, 1, ?) = ?",
                (resolved_str, len(prefix), prefix),
            ).fetchone()
            db_count = row[0] if row else 0

        physical_count = self._count_physical_files(resolved_root)
        return db_count != physical_count

    def create_or_update_index(
        self,
        root_path: Path,
        depth: int = 5,
        exclude_patterns: list[str] | None = None,
        respect_gitignore: bool = True,
    ) -> tuple[int, int]:
        """Build or incrementally update the index for root_path.

        Returns:
            Tuple of (num_added, num_deleted).
        """
        resolved_root = Path(root_path).resolve()
        resolved_str = str(resolved_root)
        prefix = resolved_str if resolved_str.endswith(os.sep) else resolved_str + os.sep

        # Scan the physical directory
        candidates = scan_directory(
            resolved_root,
            depth=depth,
            exclude_patterns=exclude_patterns,
            respect_gitignore=respect_gitignore,
        )
        # Also include the root itself if it matches the criteria
        candidates.append(resolved_root)

        current_time = time.time()

        with self._connection() as conn:
            # Get existing paths in the index under resolved_root
            existing_rows = conn.execute(
                "SELECT path, mtime, size FROM paths WHERE path = ? OR SUBSTR(path, 1, ?) = ?",
                (resolved_str, len(prefix), prefix),
            ).fetchall()
            existing_map = {row["path"]: (row["mtime"], row["size"]) for row in existing_rows}

            # Determine candidates to insert/update
            to_insert = []
            seen_candidates = set()

            for p in candidates:
                p_str = str(p)
                if p_str in seen_candidates:
                    continue
                seen_candidates.add(p_str)

                try:
                    stat = p.stat()
                    mtime = stat.st_mtime
                    size = stat.st_size if p.is_file() else 0
                except Exception:
                    continue

                is_dir = 1 if p.is_dir() else 0

                # Check if it needs update (not in DB, or mtime/size changed)
                if p_str not in existing_map or existing_map[p_str] != (mtime, size):
                    tokens = " ".join(normalize_tokens(p.name))
                    phonetic = self._compute_phonetic_codes(p.name)
                    to_insert.append(
                        (p_str, p.name, str(p.parent), mtime, size, is_dir, tokens, phonetic)
                    )

            # Determine paths to delete (in DB but no longer physical candidates)
            candidate_strs = {str(p) for p in candidates}
            to_delete = [p_str for p_str in existing_map if p_str not in candidate_strs]

            # Perform DB transactions
            if to_delete:
                conn.executemany("DELETE FROM paths WHERE path = ?", [(p,) for p in to_delete])

            if to_insert:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO paths
                    (path, basename, parent_dir, mtime, size, is_dir, tokens, phonetic)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    to_insert,
                )

            # Update indexed roots
            conn.execute(
                "INSERT OR REPLACE INTO indexed_roots (path, indexed_at) VALUES (?, ?)",
                (resolved_str, current_time),
            )

        return len(to_insert), len(to_delete)

    def get_candidates(self, root_path: Path) -> list[Path]:
        """Fetch all candidates belonging to root_path from the SQLite database."""
        resolved_root = Path(root_path).resolve()
        resolved_str = str(resolved_root)
        prefix = resolved_str if resolved_str.endswith(os.sep) else resolved_str + os.sep
        candidates = []

        with self._connection() as conn:
            rows = conn.execute(
                "SELECT path FROM paths WHERE path = ? OR SUBSTR(path, 1, ?) = ? ORDER BY path",
                (resolved_str, len(prefix), prefix),
            ).fetchall()
            for row in rows:
                candidates.append(Path(row["path"]))

        # Remove the root path itself from search candidates to match scan_directory behavior
        return [c for c in candidates if c != resolved_root]
