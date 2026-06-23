"""Shared Rich consoles for sempath terminal output."""

from __future__ import annotations

import sys
from rich.console import Console

# Reconfigure stdout/stderr on Windows/legacy terminals to prevent UnicodeEncodeError
for stream in (sys.stdout, sys.stderr):
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)
