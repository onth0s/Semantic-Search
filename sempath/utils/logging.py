"""Logging utilities for sempath."""

from __future__ import annotations

import click


def is_verbose() -> bool:
    """Check if the verbose flag is enabled in the current Click context."""
    ctx = click.get_current_context(silent=True)
    return ctx.obj.get("verbose", False) if ctx and ctx.obj else False


def verbose_log(message: str) -> None:
    """Print a message to the error console if the verbose flag is enabled."""
    if is_verbose():
        from sempath.utils.console import err_console

        err_console.print(message)
