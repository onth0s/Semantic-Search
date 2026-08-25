"""Configuration management subcommands for the sempath CLI."""

from __future__ import annotations

import sys

import click

from sempath.config import save_config
from sempath.utils.console import console, err_console


def register_config_commands(cli_group: click.Group) -> None:
    """Register the config subgroup and commands."""

    @cli_group.group()
    def config() -> None:
        """Manage the persistent configuration settings."""

    @config.command("verbose")
    @click.argument(
        "value", type=click.Choice(["on", "off", "true", "false"], case_sensitive=False)
    )
    def config_verbose(value: str) -> None:
        """Enable or disable verbose output globally."""
        is_verbose = value.lower() in ("on", "true")
        try:
            save_config({"verbose": is_verbose})
            status_str = "enabled" if is_verbose else "disabled"
            console.print(
                f"[bold green]✔ Success:[/] Verbose logging has been [bold]{status_str}[/]."
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error updating configuration:[/] {exc}")
            sys.exit(1)

    @config.command("gitignore")
    @click.argument(
        "value", type=click.Choice(["on", "off", "true", "false"], case_sensitive=False)
    )
    def config_gitignore(value: str) -> None:
        """Enable or disable respecting .gitignore rules globally."""
        respect = value.lower() in ("on", "true")
        try:
            save_config({"index": {"respect_gitignore": respect}})
            status_str = "enabled" if respect else "disabled"
            console.print(
                "[bold green]✔ Success:[/] Respecting .gitignore rules has been "
                f"[bold]{status_str}[/]."
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error updating configuration:[/] {exc}")
            sys.exit(1)

    @config.command("depth")
    @click.argument("value", type=int)
    def config_depth(value: int) -> None:
        """Set default traversal search depth globally."""
        if value < 1:
            err_console.print("[bold red]Error:[/] Depth must be a positive integer (>= 1).")
            sys.exit(1)
        try:
            save_config({"depth": value})
            console.print(
                f"[bold green]✔ Success:[/] Default search depth set to [bold]{value}[/]."
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error updating configuration:[/] {exc}")
            sys.exit(1)
