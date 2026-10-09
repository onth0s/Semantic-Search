"""Unit tests for sempath.utils.clipboard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sempath.utils.clipboard import copy_to_clipboard


def test_copy_to_clipboard_empty():
    assert copy_to_clipboard("") is False


def test_copy_to_clipboard_win32_success():
    with (
        patch("sys.platform", "win32"),
        patch("subprocess.Popen") as mock_popen,
    ):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc
        assert copy_to_clipboard("test_text") is True
        mock_popen.assert_called_once()


def test_copy_to_clipboard_failure():
    with (
        patch("sys.platform", "win32"),
        patch("subprocess.Popen", side_effect=OSError("clipboard error")),
    ):
        assert copy_to_clipboard("test_text") is False
