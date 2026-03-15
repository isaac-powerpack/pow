import click
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from ..common.utils import console
from ..core.asset_manager import AssetManager, AssetError


@click.group(name="asset")
def asset_group():
    """Manage Isaac Sim assets."""
    pass


@asset_group.command(name="set")
@click.argument("assets_path")
def set_cmd(assets_path: str):
    """Set the local asset path for pow.

    \b
    ASSETS_PATH  Absolute or relative path to the local assets directory.

    \b
    What this command does:
      1. Validates the given path exists.
      2. Creates a symlink at ~/.pow/assets → ASSETS_PATH.
      3. Writes the [asset] config in ~/.pow/system.toml.
      4. Registers a 'pow-assets' alias in omniverse.toml.
    """
    manager = AssetManager()
    try:
        abs_path = manager.set_local_asset_path(assets_path)

        details = Table.grid(padding=(0, 2))
        details.add_column(style="dim")
        details.add_column()
        details.add_row("Assets path     :", f"[bold cyan]{abs_path}[/bold cyan]")
        details.add_row("Symlink         :", f"[dim]{manager.get_assets_symlink_path()}[/dim]")
        details.add_row("Assets alias    :", f"[dim]{manager.POW_ASSETS_ALIAS}[/dim]")

        console.print(
            Panel(
                details,
                title="[bold green]✔  Asset path configured[/bold green]",
                border_style="green",
            )
        )
    except AssetError as e:
        console.print(
            Panel(
                f"[bold red]✘[/bold red]  {e}",
                title="[bold red]Asset Error[/bold red]",
                border_style="red",
            )
        )
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[bold red]✘ Unexpected error:[/bold red] {e}")
        raise SystemExit(1)


@asset_group.command(name="unset")
def unset_cmd():
    """Remove the local asset path configuration.

    \b
    What this command does:
      1. Removes the ~/.pow/assets symlink.
      2. Clears [asset] config in ~/.pow/system.toml.
      3. Removes [alias] section from omniverse.toml.
      4. Removes asset-related keys from isaacsim.exp.base.kit [settings].

    Each step is performed independently — a failure in one step does not
    prevent the others from running.
    """
    manager = AssetManager()
    try:
        results = manager.unset_local_asset_path()

        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim", min_width=34)
        grid.add_column()

        for label, outcome in results.items():
            safe_outcome = escape(outcome)
            if "skipped" in outcome.lower():
                icon = "[yellow]–[/yellow]"
                outcome_markup = f"[dim]{safe_outcome}[/dim]"
            elif "failed" in outcome.lower():
                icon = "[bold red]✘[/bold red]"
                outcome_markup = f"[red]{safe_outcome}[/red]"
            else:
                icon = "[bold green]✔[/bold green]"
                outcome_markup = safe_outcome
            grid.add_row(f"{icon}  [dim]{escape(label)}[/dim]", outcome_markup)

        console.print(
            Panel(
                grid,
                title="[bold green]Asset configuration removed[/bold green]",
                border_style="green",
            )
        )
    except AssetError as e:
        console.print(
            Panel(
                Text.from_markup(f"[bold yellow]⚠[/bold yellow]  ") + Text(str(e)),
                title="[bold yellow]Nothing to unset[/bold yellow]",
                border_style="yellow",
            )
        )
        raise SystemExit(1)
    except Exception as e:
        console.print(Text.from_markup("[bold red]✘ Unexpected error:[/bold red] ") + Text(str(e)))
        raise SystemExit(1)


@asset_group.command(name="list")
def list_cmd():
    """List available assets (placeholder)."""
    console.print("[yellow]! List command — not yet implemented.[/yellow]")
