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

    import sys

    from src.utils.mft_reader import is_admin, scan_volume_files

    # Try MFT sweep on Windows when run as Admin
    if sys.platform == "win32" and is_admin():
        drive = root_dir.drive
        if drive and drive.endswith(":"):
            vol_letter = drive[0]
            mft_candidates = scan_volume_files(vol_letter, root_dir)
            if mft_candidates is not None:
                gitignore_cache: dict[Path, pathspec.PathSpec | None] = {}

                def is_ignored_by_gitignore_mft(path: Path) -> bool:
                    curr = path
                    try:
                        if not path.is_dir():
                            curr = path.parent
                    except Exception:
                        pass

                    while True:
                        if curr not in gitignore_cache:
                            gi_file = curr / ".gitignore"
                            if gi_file.is_file():
                                try:
                                    with open(gi_file, encoding="utf-8") as f:
                                        gitignore_cache[curr] = pathspec.PathSpec.from_lines(
                                            "gitignore", f
                                        )
                                except Exception:
                                    gitignore_cache[curr] = None
                            else:
                                gitignore_cache[curr] = None

                        spec = gitignore_cache[curr]
                        if spec is not None:
                            try:
                                rel_path = path.relative_to(curr)
                                rel_path_str = str(rel_path).replace("\\", "/")
                                try:
                                    if path.is_dir():
                                        rel_path_str += "/"
                                except Exception:
                                    pass
                                if spec.match_file(rel_path_str):
                                    return True
                            except ValueError:
                                pass

                        if curr == root_dir or curr == curr.parent:
                            break
                        curr = curr.parent
                    return False

                filtered: list[Path] = []
                skipped_rel_dirs: set[str] = set()

                # Process candidates sorted by depth (number of path components)
                # to prune hidden or excluded subtrees before visiting their children
                sorted_candidates = sorted(mft_candidates, key=lambda p: len(p.parts))

                for p in sorted_candidates:
                    try:
                        rel_path = p.relative_to(root_dir)
                    except ValueError:
                        continue

                    parts = rel_path.parts
                    if len(parts) > depth:
                        continue

                    # Check if any ancestor or the path itself is hidden or excluded
                    ignored = False
                    for i in range(1, len(parts) + 1):
                        ancestor_rel = "\\".join(parts[:i])
                        if ancestor_rel in skipped_rel_dirs:
                            ignored = True
                            break

                        part = parts[i - 1]
                        if part.startswith(".") or part in exclude_patterns:
                            skipped_rel_dirs.add(ancestor_rel)
                            ignored = True
                            break

                    if ignored:
                        continue

                    # Check gitignore
                    if respect_gitignore and is_ignored_by_gitignore_mft(p):
                        try:
                            if p.is_dir():
                                skipped_rel_dirs.add(str(rel_path))
                        except Exception:
                            pass
                        continue

                    filtered.append(p)

                return filtered

    # Fallback to standard os.walk recursive sweep
    candidates: list[Path] = []
    gitignore_cache: dict[Path, pathspec.PathSpec | None] = {}

    def is_ignored_by_gitignore(path: Path) -> bool:
        """Check if the given path is ignored by any ancestor .gitignore spec."""
        curr = path
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
