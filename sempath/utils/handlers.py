"""Handler spec parsing and validation utilities for sempath."""

from __future__ import annotations

import re

import click

_ALL_HANDLERS = ["h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8"]


def parse_handler_spec(spec: str) -> list[str]:
    """Parse a handler spec string into an ordered list of handler IDs.

    Supported formats:
    - Ranges: ``h1-6``, ``1-6``, ``h1-h6``
    - Comma-separated lists: ``h1,h3,h8``, ``1,3,8``
    - Single IDs: ``h8``, ``8``

    Raises:
        click.BadParameter: If the spec cannot be parsed or contains invalid IDs.
    """
    spec_clean = spec.strip().lstrip("-")
    handlers: list[str] = []

    # Range pattern: [h]N-[h]M
    range_m = re.fullmatch(r"h?(\d+)-h?(\d+)", spec_clean)
    if range_m:
        lo, hi = int(range_m.group(1)), int(range_m.group(2))
        handlers = [f"h{n}" for n in range(lo, hi + 1)]
        valid = [h for h in handlers if h in _ALL_HANDLERS]
        if not valid:
            raise click.BadParameter(
                f"'{spec}' is not a valid handler spec. Use e.g. --h1, --h8, --h1-6, --h2,h4,h5.",
                param_hint="--handlers",
            )
        return valid

    # Comma-separated list: h1,h3,h8 or 1,3,8
    if "," in spec_clean:
        for part in spec_clean.split(","):
            part_str = part.strip().lstrip("-")
            hid = part_str if part_str.startswith("h") else f"h{part_str}"
            if hid in _ALL_HANDLERS and hid not in handlers:
                handlers.append(hid)
        if not handlers:
            raise click.BadParameter(
                f"'{spec}' is not a valid handler spec. Use e.g. --h1, --h8, --h1-6, --h2,h4,h5.",
                param_hint="--handlers",
            )
        return handlers

    # Single handler: h8 or 8
    hid = spec_clean if spec_clean.startswith("h") else f"h{spec_clean}"
    if hid in _ALL_HANDLERS:
        return [hid]

    raise click.BadParameter(
        f"'{spec}' is not a valid handler spec. Use e.g. --h1, --h8, --h1-6, --h2,h4,h5.",
        param_hint="--handlers",
    )
