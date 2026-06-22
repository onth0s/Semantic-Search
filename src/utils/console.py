"""Shared Rich consoles for sempath terminal output."""

from __future__ import annotations

from rich.console import Console

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)
