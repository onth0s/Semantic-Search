"""SQLite-based persistent path index manager for sempath.

Allows creating, updating, listing, and removing indexed directories and files.
Stores paths, basenames, tokenized names, phonetic codes, and metadata (mtime, size)
to avoid expensive disk walks on future invocations.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import jellyfish

from src.scanner import scan_directory
from src.utils.tokenize import normalize_tokens


class IndexManager:
    """Manages the SQLite database index for paths."""

    def __init__(self, db_dir: Path) -> None:
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "index.db"
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a connection to the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        # Return rows as dictionary-like objects
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
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
            # Indexes for faster queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_paths_parent ON paths (parent_dir)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_paths_path ON paths (path)")

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
        with self._get_connection() as conn:
            # Check if this exact root is indexed
            row = conn.execute(
                "SELECT 1 FROM indexed_roots WHERE path = ?", (resolved_str,)
            ).fetchone()
            if row:
                return True

            # Check if an ancestor is indexed
            roots = conn.execute("SELECT path FROM indexed_roots").fetchall()
            for r in roots:
                r_path = Path(r["path"])
                if resolved_root.is_relative_to(r_path):
                    return True
        return False

    def get_indexed_roots(self) -> list[str]:
        """Return a list of all indexed root directories."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT path FROM indexed_roots ORDER BY path").fetchall()
            return [row["path"] for row in rows]

    def clear_index(self) -> None:
        """Clear all paths and roots from the database."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM paths")
            conn.execute("DELETE FROM indexed_roots")

    def remove_root(self, root_path: Path) -> bool:
        """Remove a root directory and all its descendants from the index."""
        resolved_root = Path(root_path).resolve()
        resolved_str = str(resolved_root)
        prefix = resolved_str + "\\"
        with self._get_connection() as conn:
            # Check if the root exists
            row = conn.execute(
                "SELECT 1 FROM indexed_roots WHERE path = ?", (resolved_str,)
            ).fetchone()
            if not row:
                return False

            # Delete descendants and root
            conn.execute("DELETE FROM indexed_roots WHERE path = ?", (resolved_str,))
            # Delete paths that are subpaths of resolved_root
            conn.execute(
                "DELETE FROM paths WHERE path = ? OR SUBSTR(path, 1, ?) = ?",
                (resolved_str, len(prefix), prefix),
            )
            return True

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
        prefix = resolved_str + "\\"

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

        with self._get_connection() as conn:
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
        prefix = resolved_str + "\\"
        candidates = []

        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT path FROM paths WHERE path = ? OR SUBSTR(path, 1, ?) = ? ORDER BY path",
                (resolved_str, len(prefix), prefix),
            ).fetchall()
            for row in rows:
                candidates.append(Path(row["path"]))

        # Remove the root path itself from search candidates to match scan_directory behavior
        return [c for c in candidates if c != resolved_root]
