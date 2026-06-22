"""Unit tests for utility functions in src/utils."""

import pytest

from src.utils.scoring import clamp_confidence, format_size
from src.utils.tokenize import normalize_tokens


def test_normalize_tokens():
    """normalize_tokens splits and normalizes strings properly."""
    assert normalize_tokens("Desktop/__MAIN") == {"desktop", "main"}
    assert normalize_tokens("the main dir on dsktp") == {"the", "main", "dir", "on", "dsktp"}
    assert normalize_tokens("") == set()
    assert normalize_tokens(None) == set()
    assert normalize_tokens("   ") == set()
    assert normalize_tokens("!!!@@@") == set()


def test_clamp_confidence():
    """clamp_confidence clamps values between 0.0 and 1.0."""
    assert clamp_confidence(1.5) == 1.0
    assert clamp_confidence(-0.3) == 0.0
    assert clamp_confidence(0.85) == 0.85
    assert clamp_confidence(0.0) == 0.0
    assert clamp_confidence(1.0) == 1.0


def test_format_size():
    """format_size formats bytes to human-readable strings with 2 decimal places."""
    assert format_size(0) == "0.00 B"
    assert format_size(1536) == "1.50 KB"
    assert format_size(2411724) == "2.30 MB"
    assert format_size(1073741824) == "1.00 GB"
    assert format_size(1099511627776) == "1.00 TB"
    assert format_size(1125899906842624) == "1.00 PB"

    # Large value formatting
    assert format_size(1125899906842624 * 1024) == "1024.00 PB"

    with pytest.raises(ValueError, match="size_bytes must be non-negative"):
        format_size(-10)
