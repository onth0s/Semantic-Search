"""Unit tests for utility functions in src/utils."""

from sempath.utils.tokenize import normalize_tokens


def test_normalize_tokens():
    """normalize_tokens splits and normalizes strings properly."""
    assert normalize_tokens("Desktop/__MAIN") == {"desktop", "main"}
    assert normalize_tokens("the main dir on dsktp") == {"the", "main", "dir", "on", "dsktp"}
    assert normalize_tokens("") == set()
    assert normalize_tokens(None) == set()
    assert normalize_tokens("   ") == set()
    assert normalize_tokens("!!!@@@") == set()
