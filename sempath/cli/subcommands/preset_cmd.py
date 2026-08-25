"""Preset management subcommands for the sempath CLI."""

from __future__ import annotations

import sys

import click
from rich.table import Table

from sempath.config import load_config, save_config
from sempath.utils.console import console, err_console
from sempath.utils.handlers import parse_handler_spec


def register_preset_commands(cli_group: click.Group) -> None:
    """Register the preset subgroup and commands."""

    @cli_group.group()
    def preset() -> None:
        """Manage handler presets (-p / --preset)."""

    @preset.command("list")
    def preset_list() -> None:
        """List all configured handler presets."""
        table = Table(title="sempath Handler Presets")
        table.add_column("Preset Name", style="bold cyan")
        table.add_column("Handler Spec", style="bold green")
        table.add_column("Resolved Handlers", style="cyan")

        try:
            cfg = load_config()
            presets = cfg.get("presets", {})
            if not presets:
                console.print("[yellow]No presets currently configured.[/]")
                return
            for name, spec in presets.items():
                try:
                    resolved = ", ".join(parse_handler_spec(str(spec)))
                except Exception:
                    resolved = "(invalid spec)"
                table.add_row(str(name), str(spec), resolved)
            console.print(table)
        except Exception as exc:
            err_console.print(f"[bold red]Error listing presets:[/] {exc}")
            sys.exit(1)

    @preset.command("get")
    @click.argument("name")
    def preset_get(name: str) -> None:
        """Get the handler spec for preset NAME."""
        try:
            cfg = load_config()
            presets = cfg.get("presets", {})
            val = presets.get(name) or presets.get(str(name))
            if val is None:
                console.print(f"[yellow]⚠[/] Preset [bold cyan]'{name}'[/] is not defined.")
                sys.exit(1)
            try:
                resolved = ", ".join(parse_handler_spec(str(val)))
            except Exception:
                resolved = "(invalid spec)"
            console.print(
                f"Preset [bold cyan]'{name}'[/]: [bold green]{val}[/] [dim]({resolved})[/]"
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error getting preset:[/] {exc}")
            sys.exit(1)

    @preset.command("set")
    @click.argument("name")
    @click.argument("spec")
    def preset_set(name: str, spec: str) -> None:
        """Set preset NAME to handler SPEC (e.g. 'sempath preset set 0 h1-6')."""
        try:
            resolved_handlers = parse_handler_spec(spec)
            cfg = load_config()
            existing_presets = dict(cfg.get("presets", {}))
            existing_presets[name] = spec
            save_config({"presets": existing_presets})
            console.print(
                f"[bold green]✔ Success:[/] Saved preset [bold cyan]'{name}'[/] -> "
                f"[bold green]'{spec}'[/] [dim]({', '.join(resolved_handlers)})[/]"
            )
        except click.BadParameter as exc:
            err_console.print(f"[bold red]Invalid handler spec:[/] {exc}")
            sys.exit(1)
        except Exception as exc:
            err_console.print(f"[bold red]Error saving preset:[/] {exc}")
            sys.exit(1)

    @preset.command("remove")
    @click.argument("name")
    def preset_remove(name: str) -> None:
        """Remove preset NAME from configuration."""
        try:
            cfg = load_config()
            existing_presets = dict(cfg.get("presets", {}))
            if name not in existing_presets and str(name) not in existing_presets:
                console.print(f"[yellow]⚠[/] Preset [bold cyan]'{name}'[/] does not exist.")
                return
            existing_presets.pop(name, None)
            existing_presets.pop(str(name), None)
            save_config({"presets": existing_presets})
            console.print(f"[bold green]✔ Success:[/] Removed preset [bold cyan]'{name}'[/].")
        except Exception as exc:
            err_console.print(f"[bold red]Error removing preset:[/] {exc}")
            sys.exit(1)
