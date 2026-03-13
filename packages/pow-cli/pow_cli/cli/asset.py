"""Asset command implementation."""

import click
import time
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

from ..common.utils import console
from ..core.config import Config
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

    config = Config()
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
def asset_list():
    """Show all available assets and their status."""
    config = Config()
    manager = AssetManager(config)
    assets = manager.list_assets()

    table = Table(title="Available Assets")
    table.add_column("Asset Name", style="cyan")
    table.add_column("Group", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Completion", style="yellow")
    table.add_column("Size", style="blue")

    # Grouping logic for the mockup
    for asset in assets:
        status_color = "green" if asset["status"] == "Installed" else "yellow"
        table.add_row(
            asset["name"],
            asset["group"],
            f"[{status_color}]{asset['status']}[/{status_color}]",
            f"{asset['completion']}%",
            asset["size"]
        )

    console.print(table)

@asset_group.command(name="add")
@click.option("-n", "--name", required=True, help="Name of the asset to add")
@click.option("--keep", help="Path to store/keep the downloaded asset")
def asset_add(name, keep):
    """Add a new asset (download and install)."""
    config = Config()
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
