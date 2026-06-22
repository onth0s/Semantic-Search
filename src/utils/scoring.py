"""Confidence scoring and formatting utilities."""

from __future__ import annotations


def clamp_confidence(value: float) -> float:
    """Clamp *value* to the ``[0.0, 1.0]`` confidence range.

    Examples::

        >>> clamp_confidence(1.5)
        1.0
        >>> clamp_confidence(-0.3)
        0.0
        >>> clamp_confidence(0.85)
        0.85
    """
    return max(0.0, min(1.0, value))


def format_size(size_bytes: int) -> str:
    """Format *size_bytes* into a human-readable string with exactly 2 decimal places.

    Uses binary units (KB = 1024 bytes, MB = 1024 KB, etc.) matching
    the project rule for file/directory size output.

    Examples::

        >>> format_size(0)
        '0.00 B'
        >>> format_size(1536)
        '1.50 KB'
        >>> format_size(2411724)
        '2.30 MB'
        >>> format_size(1073741824)
        '1.00 GB'
    """
    if size_bytes < 0:
        raise ValueError(f"size_bytes must be non-negative, got {size_bytes}")

    units = ("B", "KB", "MB", "GB", "TB", "PB")
    size = float(size_bytes)

    for unit in units:
        if abs(size) < 1024.0 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024.0

    # Unreachable, but satisfies type checkers
    return f"{size:.2f} PB"  # pragma: no cover
