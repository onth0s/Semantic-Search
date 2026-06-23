"""Unit tests for sempath.utils.mft_reader and MFT integration in scanner."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from sempath.scanner import scan_directory
from sempath.utils.mft_reader import get_mft_index, is_admin, scan_volume_files


def test_is_admin_check():
    """is_admin correctly calls windll on Windows and returns boolean."""
    if sys.platform != "win32":
        assert is_admin() is False
    else:
        with patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=1):
            assert is_admin() is True
        with patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=0):
            assert is_admin() is False
        with patch("ctypes.windll.shell32.IsUserAnAdmin", side_effect=Exception):
            assert is_admin() is False


def test_get_mft_index():
    """get_mft_index masks out the sequence number sequence properly."""
    # MFT record index is lower 48 bits
    assert get_mft_index(0x0005000000000005) == 5
    assert get_mft_index(0x1234567890ABCDEF) == 0x567890ABCDEF


def test_scan_volume_files_non_windows():
    """scan_volume_files returns None on non-Windows systems."""
    with patch("sys.platform", "linux"):
        assert scan_volume_files("C", Path("C:/Temp")) is None


@pytest.fixture
def mock_mft_paths(tmp_path: Path) -> list[Path]:
    """Provide list of mock paths for testing MFT path integration."""
    return [
        tmp_path / "file1.txt",
        tmp_path / "Desktop",
        tmp_path / "Desktop" / "notes.txt",
        tmp_path / "Desktop" / "__MAIN",
        tmp_path / "Desktop" / "__MAIN" / "principal.txt",
        tmp_path / "Desktop" / ".hidden_dir",
        tmp_path / "Desktop" / ".hidden_dir" / "file.txt",
        tmp_path / "Desktop" / "node_modules",
        tmp_path / "Desktop" / "node_modules" / "pkg.json",
        tmp_path / "Documents",
        tmp_path / "Documents" / "doc.pdf",
        tmp_path / "Documents" / "ignored.tmp",
    ]


def test_scan_directory_mft_integration(tmp_path: Path, mock_mft_paths: list[Path]):
    """scan_directory filters MFT scanner output correctly."""
    # Write a .gitignore inside Documents to ignore *.tmp
    docs_dir = tmp_path / "Documents"
    docs_dir.mkdir(exist_ok=True)
    (docs_dir / ".gitignore").write_text("*.tmp\n", encoding="utf-8")

    # Mock is_admin and scan_volume_files
    with (
        patch("sys.platform", "win32"),
        patch("sempath.utils.mft_reader.is_admin", return_value=True),
        patch("sempath.utils.mft_reader.scan_volume_files", return_value=mock_mft_paths),
    ):
        candidates = scan_directory(tmp_path, depth=5, exclude_patterns=["node_modules"])
        names = {p.name for p in candidates}

        # Assert correct files exist
        assert "file1.txt" in names
        assert "Desktop" in names
        assert "notes.txt" in names
        assert "__MAIN" in names
        assert "principal.txt" in names
        assert "Documents" in names
        assert "doc.pdf" in names

        # Assert exclusions and hidden folders/files are removed
        assert "node_modules" not in names
        assert "pkg.json" not in names
        assert ".hidden_dir" not in names
        assert "file.txt" not in names

        # Assert gitignore files are respected
        assert "ignored.tmp" not in names


def test_scan_directory_mft_depth_limit(tmp_path: Path, mock_mft_paths: list[Path]):
    """scan_directory respects depth limit on MFT paths."""
    with (
        patch("sys.platform", "win32"),
        patch("sempath.utils.mft_reader.is_admin", return_value=True),
        patch("sempath.utils.mft_reader.scan_volume_files", return_value=mock_mft_paths),
    ):
        # Depth = 1: top-level only
        candidates = scan_directory(tmp_path, depth=1)
        names = {p.name for p in candidates}

        assert "file1.txt" in names
        assert "Desktop" in names
        assert "Documents" in names
        # Deeper entries should not be present
        assert "notes.txt" not in names
        assert "principal.txt" not in names
        assert "doc.pdf" not in names
