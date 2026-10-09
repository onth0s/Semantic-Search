"""Unit tests for MFT reader utility functions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sempath.utils.mft_reader import (
    INVALID_HANDLE_VALUE,
    get_mft_index,
    is_admin,
    is_invalid_handle,
    scan_volume_files,
)


def test_is_invalid_handle():
    assert is_invalid_handle(None) is True
    assert is_invalid_handle(INVALID_HANDLE_VALUE) is True
    assert is_invalid_handle(0xFFFFFFFF) is True
    assert is_invalid_handle(12345) is False


def test_get_mft_index():
    frn = 0x0001000000000005
    assert get_mft_index(frn) == 5


def test_is_admin_non_win32():
    with patch("sys.platform", "linux"):
        assert is_admin() is False


def test_scan_volume_files_non_win32():
    with patch("sys.platform", "linux"):
        assert scan_volume_files("C", Path(".")) is None
