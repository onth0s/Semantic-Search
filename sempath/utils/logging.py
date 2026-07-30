"""Logging utilities for sempath."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

import click

_verbose_suppressed: ContextVar[bool] = ContextVar("_verbose_suppressed", default=False)


@contextmanager
def suppress_verbose() -> Generator[None, None, None]:
    """Context manager that silences verbose_log output for its duration."""
    token = _verbose_suppressed.set(True)
    try:
        yield
    finally:
        _verbose_suppressed.reset(token)


def is_verbose() -> bool:
    """Check if the verbose flag is enabled in the current Click context."""
    ctx = click.get_current_context(silent=True)
    return ctx.obj.get("verbose", False) if ctx and ctx.obj else False


def verbose_log(message: str) -> None:
    """Print a message to the error console if the verbose flag is enabled."""
    if _verbose_suppressed.get():
        return
    if is_verbose():
        from sempath.utils.console import err_console

        err_console.print(message)
