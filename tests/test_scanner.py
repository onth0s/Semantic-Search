"""Unit tests for sempath.scanner — directory walking and filtering."""

from pathlib import Path

import pytest

from sempath.scanner import scan_directory


@pytest.fixture
def temp_fs(tmp_path: Path) -> Path:
    """Create a complex temporary filesystem structure for scanner tests.

    Structure:
        root/
        ├── file1.txt
        ├── .hidden_file
        ├── .git/
        │   └── config
        ├── node_modules/
        │   └── package.json
        ├── Desktop/
        │   ├── notes.txt
        │   └── __MAIN/
        │       └── principal.txt
        └── Documents/
            ├── .gitignore
            ├── doc1.pdf
            └── ignored_file.tmp
    """
    # Top-level files & folders
    (tmp_path / "file1.txt").write_text("file1", encoding="utf-8")
    (tmp_path / ".hidden_file").write_text("hidden", encoding="utf-8")

    git = tmp_path / ".git"
    git.mkdir()
    (git / "config").write_text("git config", encoding="utf-8")

    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "package.json").write_text("{}", encoding="utf-8")

    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "notes.txt").write_text("notes", encoding="utf-8")

    main_dir = desktop / "__MAIN"
    main_dir.mkdir()
    (main_dir / "principal.txt").write_text("principal", encoding="utf-8")

    documents = tmp_path / "Documents"
    documents.mkdir()
    (documents / "doc1.pdf").write_text("pdf content", encoding="utf-8")
    (documents / "ignored_file.tmp").write_text("ignored", encoding="utf-8")

    # Add a .gitignore in Documents that ignores *.tmp files
    (documents / ".gitignore").write_text("*.tmp\n", encoding="utf-8")

    return tmp_path


def test_scan_directory_basic(temp_fs: Path):
    """scan_directory scans recursively and ignores default dotfiles/folders."""
    # Exclude nothing explicitly, just use default dot pruning
    candidates = scan_directory(temp_fs, depth=5)
    names = {p.name for p in candidates}

    # Verify standard files/dirs are present
    assert "file1.txt" in names
    assert "Desktop" in names
    assert "notes.txt" in names
    assert "__MAIN" in names
    assert "principal.txt" in names
    assert "Documents" in names
    assert "doc1.pdf" in names

    # Verify hidden/dot files/dirs are pruned
    assert ".hidden_file" not in names
    assert ".git" not in names
    assert "config" not in names


def test_scan_directory_exclusions(temp_fs: Path):
    """scan_directory respects exclude_patterns list."""
    # Exclude node_modules explicitly
    candidates = scan_directory(temp_fs, depth=5, exclude_patterns=["node_modules"])
    names = {p.name for p in candidates}

    assert "package.json" not in names
    assert "node_modules" not in names


def test_scan_directory_depth_limit(temp_fs: Path):
    """scan_directory respects depth limit."""
    # Depth = 1: top-level only
    candidates = scan_directory(temp_fs, depth=1)
    names = {p.name for p in candidates}

    assert "file1.txt" in names
    assert "Desktop" in names
    assert "Documents" in names
    # Deeper files should NOT be present
    assert "notes.txt" not in names
    assert "__MAIN" not in names
    assert "principal.txt" not in names


def test_scan_directory_respects_gitignore(temp_fs: Path):
    """scan_directory respects dynamic gitignore rules in subdirectories."""
    candidates = scan_directory(temp_fs, depth=5, respect_gitignore=True)
    names = {p.name for p in candidates}

    # doc1.pdf is not ignored
    assert "doc1.pdf" in names
    # ignored_file.tmp is ignored by Documents/.gitignore
    assert "ignored_file.tmp" not in names
    # The .gitignore itself should be skipped because it starts with a dot
    assert ".gitignore" not in names
