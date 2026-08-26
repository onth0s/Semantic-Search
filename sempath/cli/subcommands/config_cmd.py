"""Configuration management subcommands for the sempath CLI."""

from __future__ import annotations

import sys

import click
from rich.table import Table

from sempath.config import (
    _APPDATA_CONFIG,
    _BUNDLED_CONFIG,
    get_index_store_path,
    load_config,
    save_config,
)
from sempath.constants import DEFAULT_DEPTH
from sempath.utils.console import console, err_console


def register_config_commands(cli_group: click.Group) -> None:
    """Register the config subgroup and commands."""

    @cli_group.group(invoke_without_command=True)
    @click.pass_context
    def config(ctx: click.Context) -> None:
        """Manage the persistent configuration settings.

        Run 'sempath config list' or 'sempath config' to display all active settings.
        """
        if ctx.invoked_subcommand is None:
            ctx.invoke(config_list)

    @config.command("list")
    def config_list() -> None:
        """List all active configuration settings and defaults."""
        try:
            cfg = load_config()

            table = Table(title="sempath Configuration Settings")
            table.add_column("Setting", style="bold cyan")
            table.add_column("Active Value", style="bold green")
            table.add_column("Default", style="dim")
            table.add_column("Description", style="dim")

            depth_val = cfg.get("depth", DEFAULT_DEPTH)
            depth_display = "unlimited (-1)" if depth_val == -1 else str(depth_val)
            table.add_row(
                "depth",
                depth_display,
                str(DEFAULT_DEPTH),
                "Default folder traversal depth",
            )

            verbose_val = cfg.get("verbose", True)
            table.add_row(
                "verbose",
                "enabled (on)" if verbose_val else "disabled (off)",
                "enabled (on)",
                "Diagnostic under-the-hood logging",
            )

            respect_gi = cfg.get("index", {}).get("respect_gitignore", False)
            table.add_row(
                "index.respect_gitignore",
                "enabled (on)" if respect_gi else "disabled (off)",
                "disabled (off)",
                "Respect .gitignore rules during scan",
            )

            auto_index = cfg.get("index", {}).get("auto", True)
            table.add_row(
                "index.auto",
                "enabled" if auto_index else "disabled",
                "enabled",
                "Auto-build and use SQLite index",
            )

            index_store = str(get_index_store_path(cfg))
            table.add_row(
                "index.store",
                index_store,
                "%APPDATA%\\sempath\\cache",
                "SQLite index cache storage folder",
            )

            enabled_h = ", ".join(cfg.get("handlers", {}).get("enabled", []))
            table.add_row(
                "handlers.enabled",
                enabled_h,
                "h1-h8",
                "Active Chain of Responsibility handlers",
            )

            console.print(table)

            # Show configuration source path
            if _APPDATA_CONFIG.exists():
                console.print(f"[dim]User config file:[/] [cyan]{_APPDATA_CONFIG}[/]")
            elif _BUNDLED_CONFIG.exists():
                console.print(f"[dim]Bundled config file:[/] [cyan]{_BUNDLED_CONFIG}[/]")
            else:
                console.print("[dim]Using built-in default configuration.[/]")

        except Exception as exc:
            err_console.print(f"[bold red]Error listing configuration:[/] {exc}")
            sys.exit(1)

    @config.command("show")
    @click.pass_context
    def config_show(ctx: click.Context) -> None:
        """Alias for 'config list' — display active configuration settings."""
        ctx.invoke(config_list)

    @config.command("verbose")
    @click.argument(
        "value",
        type=click.Choice(["on", "off", "true", "false"], case_sensitive=False),
        required=False,
        default=None,
    )
    def config_verbose(value: str | None) -> None:
        """Get or set global verbose logging."""
        try:
            cfg = load_config()
            if value is None:
                is_verbose = cfg.get("verbose", True)
                status_str = "enabled (on)" if is_verbose else "disabled (off)"
                console.print(f"Current verbose logging: [bold green]{status_str}[/]")
                return

            is_verbose = value.lower() in ("on", "true")
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
        "value",
        type=click.Choice(["on", "off", "true", "false"], case_sensitive=False),
        required=False,
        default=None,
    )
    def config_gitignore(value: str | None) -> None:
        """Get or set global .gitignore compliance."""
        try:
            cfg = load_config()
            if value is None:
                respect = cfg.get("index", {}).get("respect_gitignore", False)
                status_str = "enabled (on)" if respect else "disabled (off)"
                console.print(f"Current respect .gitignore setting: [bold green]{status_str}[/]")
                return

            respect = value.lower() in ("on", "true")
            save_config({"index": {"respect_gitignore": respect}})
            status_str = "enabled" if respect else "disabled"
            console.print(
                "[bold green]✔ Success:[/] Respecting .gitignore rules has been "
                f"[bold]{status_str}[/]."
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error updating configuration:[/] {exc}")
            sys.exit(1)

    @config.command(
        "depth",
        context_settings={"ignore_unknown_options": True, "allow_interspersed_args": False},
    )
    @click.argument("value", type=str, required=False, default=None)
    def config_depth(value: str | None) -> None:
        """Get or set default search depth (-1 for unlimited)."""
        try:
            cfg = load_config()
            if value is None:
                depth_val = cfg.get("depth", DEFAULT_DEPTH)
                display_val = "unlimited (-1)" if depth_val == -1 else str(depth_val)
                console.print(f"Current default search depth: [bold green]{display_val}[/]")
                return

            try:
                val_int = int(value)
            except ValueError:
                err_console.print(
                    "[bold red]Error:[/] Depth must be a valid integer (>= 1 or -1 for unlimited)."
                )
                sys.exit(1)

            if val_int < 1 and val_int != -1:
                err_console.print(
                    "[bold red]Error:[/] Depth must be a positive integer (>= 1) "
                    "or -1 for unlimited."
                )
                sys.exit(1)

            save_config({"depth": val_int})
            display_val = "unlimited (-1)" if val_int == -1 else str(val_int)
            console.print(
                f"[bold green]✔ Success:[/] Default search depth set to [bold]{display_val}[/]."
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error updating configuration:[/] {exc}")
            sys.exit(1)
