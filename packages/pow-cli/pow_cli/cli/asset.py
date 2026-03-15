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
    console.print()
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
    console.print()
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


@asset_group.command(name="info")
def info_cmd():
    """Show details about the current local asset configuration."""
    manager = AssetManager()
    console.print()
    try:
        data = manager.get_asset_list_data()
        _print_asset_status_panel(data)
    except Exception as e:
        console.print(Text.from_markup("[bold red]✘ Failed to load asset data:[/bold red] ") + Text(str(e)))
        raise SystemExit(1)


@asset_group.command(name="list")
@click.option("-n", "--name", "view", flag_value="name", default=True, help="List by asset name (default).")
@click.option("-g", "--group", "view", flag_value="group", help="List aggregated by group.")
def list_cmd(view: str):
    """List available Isaac Sim 5.1.0 assets.

    \b
    Views:
      -n / --name   Show each asset individually, grouped by header (default).
      -g / --group  Show one row per group with summed size.
    """
    manager = AssetManager()
    console.print()
    try:
        data = manager.get_asset_list_data()
    except Exception as e:
        console.print(Text.from_markup("[bold red]✘ Failed to load asset data:[/bold red] ") + Text(str(e)))
        raise SystemExit(1)

    if view == "name":
        _print_name_view(data)
    else:
        _print_group_view(data)


# ── View renderers ────────────────────────────────────────────────────────────


def _print_asset_status_panel(data: "AssetListData") -> None:  # noqa: F821
    from rich.columns import Columns

    if not data.local_path:
        console.print(
            Panel(
                "[dim]○  Local assets not configured  —  run [bold]pow asset set <path>[/bold] to configure[/dim]",
                title="[dim]Status[/dim]",
                border_style="dim",
                padding=(1, 2),
            )
        )
        console.print()
        return

    manager = AssetManager()
    symlink_path = manager.get_assets_symlink_path()
    
    status_text = "[bold green]Active[/bold green]"
    dot = "[bold green]●[/bold green]"
    
    if not data.symlink_ok:
        status_text = "[bold red]Broken Link[/bold red]"
        dot = "[bold red]●[/bold red]"

    grid = Table.grid(padding=(0, 2))
    grid.add_column(justify="right", style="dim")
    grid.add_column()

    grid.add_row("Status", f"{dot}  {status_text}")
    grid.add_row("Location", f"[bold cyan]{escape(data.local_path)}[/bold cyan]")
    
    symlink_status = "[green]✔ valid[/green]" if data.symlink_ok else "[bold red]✘ broken[/bold red]"
    grid.add_row("Symlink", f"[dim]{escape(str(symlink_path))}[/dim]  ({symlink_status})")

    console.print(
        Panel(
            grid,
            title="[bold blue]Local Asset Configuration[/bold blue]",
            border_style="blue" if data.symlink_ok else "red",
            padding=(1, 2),
        )
    )
    console.print()


def _status_style(status: str, compact: bool = False) -> str:
    """Return a Rich-markup-wrapped status string."""
    style_map = {
        "downloaded":     "green",
        "in-progress":    "yellow",
        "not-downloaded": "dim",
        "partial":        "yellow",
        "error":          "bold red",
        # Snippet mappings
        "installed":      "green",
        "not loaded":     "dim",
    }
    
    clean_status = status.lower()
    # Map internal statuses to user-requested snippets labels if needed
    label = status
    if clean_status == "downloaded": label = "Installed"
    elif clean_status == "not-downloaded": label = "Not Loaded"
    elif clean_status == "in-progress": label = "In-Progress"
    
    color = style_map.get(clean_status, style_map.get(label.lower(), "white"))
    
    if compact:
        return f"[{color}]{label}[/{color}]"
    return f"[bold {color}]{escape(label)}[/bold {color}]" if "bold" not in color else f"[{color}]{escape(label)}[/{color}]"


def _pct_str(pct: float) -> str:
    if pct <= 0:
        return "[dim]—[/dim]"
    if pct >= 100:
        return "[green]100%[/green]"
    return f"[yellow]{pct:.0f}%[/yellow]"


def _print_name_view(data: "AssetListData") -> None:  # noqa: F821
    from itertools import groupby
    from collections import defaultdict
    
    table = Table(title="Available Assets (by Name)")
    table.add_column("Asset Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Completion", style="yellow")
    table.add_column("Size", style="blue")

    sorted_entries = sorted(data.entries, key=lambda e: (e.group_name, e.title))
    
    for group_name, group_iter in groupby(sorted_entries, key=lambda e: e.group_name):
        group_assets = list(group_iter)
        
        names = [f"[bold magenta]{escape(group_name)}[/bold magenta]"]
        statuses = [""]
        completions = [""]
        sizes = [""]

        for asset in sorted(group_assets, key=lambda e: e.title):
            names.append(f"  {escape(asset.title)}")
            
            # Use compact style for multi-line block
            statuses.append(_status_style(asset.status, compact=True))
            completions.append(_pct_str(asset.completion_pct))
            sizes.append(escape(asset.size))

        table.add_row(
            "\n".join(names),
            "\n".join(statuses),
            "\n".join(completions),
            "\n".join(sizes),
            end_section=True
        )

    console.print(table)
    console.print()


def _print_group_view(data: "AssetListData") -> None:  # noqa: F821
    from itertools import groupby

    table = Table(title="Asset Groups (Aggregated)")
    table.add_column("Group Name", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Completion", style="yellow")
    table.add_column("Size", style="blue")

    sorted_entries = sorted(data.entries, key=lambda e: e.group_name)

    for group_name, group_iter in groupby(sorted_entries, key=lambda e: e.group_name):
        group_entries = list(group_iter)

        total_assets = len(group_entries)
        installed_count = sum(1 for e in group_entries if e.status.lower() == "downloaded")
        in_progress_count = sum(1 for e in group_entries if e.status.lower() == "in-progress")

        if installed_count == total_assets:
            status = "Installed"
        elif installed_count > 0 or in_progress_count > 0:
            status = "Partial"
        else:
            status = "Not Loaded"

        percent = int((installed_count / total_assets) * 100) if total_assets > 0 else 0

        # Aggregate size
        total_gb = 0.0
        for e in group_entries:
            try:
                s = e.size.upper()
                if "GB" in s:
                    total_gb += float(s.replace("GB", "").strip())
                elif "MB" in s:
                    total_gb += float(s.replace("MB", "").strip()) / 1024
                else:
                    total_gb += float(s.split()[0])
            except (ValueError, IndexError):
                pass
        size_str = f"{total_gb:.2f} GB" if total_gb > 0 else "—"

        table.add_row(
            escape(group_name),
            _status_style(status, compact=True),
            _pct_str(percent),
            size_str
        )

    console.print(table)
    console.print()
