"""Asset command implementation."""

import click
import time
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

from ..common.utils import console
from ..core.models.pow_config import PowConfig
from ..core.asset_manager import AssetManager

@click.group(name="asset")
def asset_group():
    """Manage Isaac Sim and Omniverse assets."""
    pass

@asset_group.command(name="init")
@click.option("--target", "-t", help="Target folder name to store local assets")
def asset_init(target):
    """Initialize asset directory and tracking."""
    console.print("[bold blue]🚀 Initializing asset tracking system...[/bold blue]")
    
    if not target:
        target = click.prompt("Enter target folder name to store local assets", default="assets")

    config = PowConfig()
    manager = AssetManager(config)
    
    # 1. Ensure global folder exists
    manager.ensure_global_assets()
    
    # 2. Initialize local assets and symlink
    result = manager.initialize_local_assets(target)

    console.print(f"  [green]✔[/green] Created local assets folder: [cyan]{result['local_path']}[/cyan]")
    console.print(f"  [green]✔[/green] Created local profile: [cyan]{result['profile_file']}[/cyan]")
    console.print(f"  [green]✔[/green] Created global config: [cyan]{result['config_file']}[/cyan]")
    console.print(f"  [green]✔[/green] Symlinked project to global assets: [cyan]{result['symlink_path']}[/cyan]")
    console.print("\n[bold green]✅ Asset system initialized successfully.[/bold green]")

@asset_group.command(name="list")
@click.option("--name", "-n", is_flag=True, help="Display asset name table (default)")
@click.option("--group", "-g", is_flag=True, help="Display group table with aggregated sizes")
def asset_list(name, group):
    """Show available assets and their status."""
    config = PowConfig()
    manager = AssetManager(config)
    assets = manager.list_assets()

    # Default to name view if neither or both are specified
    if not group:
        name = True

    if name:
        table = Table(title="Available Assets (by Name)")
        table.add_column("Asset Name", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Completion", style="yellow")
        table.add_column("Size", style="blue")

        # Group assets by category for consolidated rows
        from collections import defaultdict
        category_groups = defaultdict(list)
        for asset in assets:
            category_groups[asset["category"]].append(asset)

        for cat_name, group_assets in category_groups.items():
            names = [f"[bold magenta]{cat_name}[/bold magenta]"]
            statuses = [""]
            completions = [""]
            sizes = [""]

            for asset in group_assets:
                names.append(f"  {asset['slug']}")
                status_color = "green" if asset["status"] == "Installed" else "yellow"
                statuses.append(f"[{status_color}]{asset['status']}[/{status_color}]")
                completions.append(f"{asset['completion']}%")
                sizes.append(asset["size"])

            table.add_row(
                "\n".join(names),
                "\n".join(statuses),
                "\n".join(completions),
                "\n".join(sizes),
                end_section=True
            )
        console.print(table)

    elif group:
        table = Table(title="Asset Groups (Aggregated)")
        table.add_column("Group Name", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Completion", style="yellow")
        table.add_column("Size", style="blue")

        # Aggregate data by category key
        groups = {}
        for asset in assets:
            cat_name = asset["category"]
            if cat_name not in groups:
                groups[cat_name] = {"size": 0.0, "installed": 0, "total": 0}
            
            groups[cat_name]["size"] += manager._parse_size(asset["size"])
            groups[cat_name]["total"] += 1
            if asset["status"] == "Installed":
                groups[cat_name]["installed"] += 1

        for cat_name, data in groups.items():
            status = "Installed" if data["installed"] == data["total"] else "Partial" if data["installed"] > 0 else "Not Loaded"
            status_color = "green" if status == "Installed" else "yellow" if status == "Partial" else "dim"
            percent = int((data["installed"] / data["total"]) * 100)
            
            table.add_row(
                cat_name,
                f"[{status_color}]{status}[/{status_color}]",
                f"{percent}%",
                f"{data['size']:.2f} GB"
            )
        console.print(table)

@asset_group.command(name="add")
@click.option("-n", "--name", required=True, help="Name of the asset to add")
@click.option("--keep", help="Path to store/keep the downloaded asset")
def asset_add(name, keep):
    """Add a new asset (download and install)."""
    config = PowConfig()
    manager = AssetManager(config)
    
    console.print(f"[bold blue]📦 Adding asset: [cyan]{name}[/cyan][/bold blue]")
    
    result = manager.add_asset(name, keep)
    
    if result["status"] == "already_installed":
        console.print(f"[yellow]⚠ {result['message']}[/yellow]")
        return

    # Mocking a download and unzip process
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task1 = progress.add_task(f"[cyan]Downloading {name}...", total=100)
        while not progress.finished:
            progress.update(task1, advance=20)
            time.sleep(0.3)

    console.print(f"  [green]✔[/green] Extracted into: [cyan]{result['extracted_to']}[/cyan]")
    
    if keep:
        console.print(f"  [green]✔[/green] Original file kept at: [cyan]{result['path']}[/cyan]")
    else:
        console.print(f"  [green]✔[/green] Original file kept at: [cyan]~/Downloads[/cyan] (default)")

    console.print(f"\n[bold green]✅ Asset '{name}' installed successfully.[/bold green]")
