"""Directory scanner for sempath.

Traverses the filesystem recursively from a root directory up to a maximum
depth, filtering out excluded patterns, hidden files/directories, and
respecting dynamic nested .gitignore rules using the pathspec library.
"""

from __future__ import annotations

import os
from pathlib import Path

import pathspec


def scan_directory(
    root_dir: Path,
    depth: int = 5,
    exclude_patterns: list[str] | None = None,
    respect_gitignore: bool = True,
) -> list[Path]:
    """Scan root_dir recursively and return a list of candidate Paths.

    Args:
        root_dir: The directory to start scanning from.
        depth: The maximum directory depth to traverse (default: 5).
        exclude_patterns: List of folder names to exclude (e.g. ['node_modules', '.git']).
        respect_gitignore: If True, respect local .gitignore files (default: True).

    Returns:
        List of Path objects found during the scan.
    """
    if exclude_patterns is None:
        exclude_patterns = []

    root_dir = Path(root_dir).resolve()
    if not root_dir.exists() or not root_dir.is_dir():
        return []

    candidates: list[Path] = []
    gitignore_cache: dict[Path, pathspec.PathSpec | None] = {}

    def is_ignored_by_gitignore(path: Path) -> bool:
        """Check if the given path is ignored by any ancestor .gitignore spec."""
        curr = path
        # Walk up from the path's parent to the root_dir (inclusive)
        if not path.is_dir():
            curr = path.parent

        while True:
            if curr not in gitignore_cache:
                gi_file = curr / ".gitignore"
                if gi_file.is_file():
                    try:
                        with open(gi_file, encoding="utf-8") as f:
                            gitignore_cache[curr] = pathspec.PathSpec.from_lines("gitignore", f)
                    except Exception:
                        gitignore_cache[curr] = None
                else:
                    gitignore_cache[curr] = None

            spec = gitignore_cache[curr]
            if spec is not None:
                try:
                    rel_path = path.relative_to(curr)
                    rel_path_str = str(rel_path).replace("\\", "/")
                    if path.is_dir():
                        rel_path_str += "/"
                    if spec.match_file(rel_path_str):
                        return True
                except ValueError:
                    pass

            if curr == root_dir or curr == curr.parent:
                break
            curr = curr.parent
        return False

    for root, dirs, files in os.walk(root_dir):
        # Calculate current depth relative to root_dir
        rel_path = Path(root).relative_to(root_dir)
        curr_depth = len(rel_path.parts)

        # If we have reached the max depth, do not walk any deeper
        if curr_depth >= depth:
            dirs.clear()
            continue

        # Filter directories in-place to control traversal
        kept_dirs = []
        for d in dirs:
            # Skip hidden directories and matches in exclude_patterns
            if d.startswith(".") or d in exclude_patterns:
                continue
            dir_path = Path(root) / d
            if respect_gitignore and is_ignored_by_gitignore(dir_path):
                continue
            kept_dirs.append(d)
            candidates.append(dir_path)
        dirs[:] = kept_dirs

        # Process files in current directory
        for f in files:
            # Skip hidden files and matches in exclude_patterns
            if f.startswith(".") or f in exclude_patterns:
                continue
            file_path = Path(root) / f
            if respect_gitignore and is_ignored_by_gitignore(file_path):
                continue
            candidates.append(file_path)

    return candidates
