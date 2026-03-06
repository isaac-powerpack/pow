"""Pow CLI - Root commands."""

import click


@click.group()
def pow_group():
    """Isaac Powerpack CLI for Isaac ROS and Isaac Sim development."""
    pass


import os
import time
from pathlib import Path
import tomllib
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm
from rich.table import Table
from rich import print as rprint

console = Console()


def get_global_dir_name():
    """Read global_dir_name from pyproject.toml or default to .pow"""
    pyproject_path = Path.cwd() / "pyproject.toml"
    if pyproject_path.exists():
        with open(pyproject_path, "rb") as f:
            try:
                data = tomllib.load(f)
                return data.get("tool", {}).get("pow-cli", {}).get("global_dir_name", ".pow")
            except Exception:
                pass
    return ".pow"


@pow_group.command()
def init():
    """Initialize Isaac ROS project (Mockup with Rich)."""
    global_dir_name = get_global_dir_name()
    home = Path.home()
    global_path = home / global_dir_name

    console.print(Panel.fit(
        "[bold cyan]🚀 Isaac Powerpack Initialization[/bold cyan]",
        subtitle="[dim]Setting up your Isaac ROS & Sim environment[/dim]"
    ))

    # Step 1: Config Info
    console.print(f"\n[bold blue]1. Config:[/bold blue] Using global directory [bold green]'{global_dir_name}'[/bold green]")
    
    # Step 2: Global Directory Structure
    console.print(f"[bold blue]2. Workspace:[/bold blue] Preparing [dim]{global_path}[/dim]...")
    subfolders = ["app", "modules", "projects", "sim-ros"]
    table = Table(show_header=False, box=None, padding=(0, 2))
    for sub in subfolders:
        table.add_row(f"[green]✔[/green] Created", f"{global_dir_name}/{sub}")
    console.print(table)

    # Step 3: Conflict Check
    if Path("pow.toml").exists():
        console.print(f"[bold blue]3. Conflict Check:[/bold blue] [yellow]Found existing pow.toml[/yellow]")
        if not Confirm.ask("   Do you want to override existing pow.toml and re-initialize?", default=False):
            console.print("\n[yellow]Skipping initialization of pow.toml.[/yellow]")
            return
    else:
        console.print(f"[bold blue]3. Conflict Check:[/bold blue] No existing pow.toml found. Proceeding...")

    # Step 4: ROS Integration
    console.print(f"[bold blue]4. ROS Integration:[/bold blue]")
    if Confirm.ask("   Enable ROS integration?", default=True):
        with console.status("[bold green]Cloning Isaac ROS workspace..."):
            time.sleep(1.5)  # Simulated delay
            console.print(f"   [green]✔[/green] Cloned IsaacSim-ros_workspaces to {global_dir_name}/sim-ros")
        
        with console.status("[bold green]Building Isaac ROS workspace in Docker..."):
            time.sleep(2)  # Simulated delay
            console.print("   [green]✔[/green] Build complete.")

    # Step 5: Local Project Structure
    console.print(f"[bold blue]5. Project Structure:[/bold blue] Creating local folders...")
    local_folders = ["exts", "scripts", ".modules", ".assets", "standalone"]
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task(description="Setting up project folders...", total=len(local_folders))
        for folder in local_folders:
            time.sleep(0.3)
            progress.update(task, advance=1, description=f"Created ./{folder}")
    
    console.print("   [green]✔[/green] Local folders created.")
    console.print("   [green]✔[/green] Created .gitignore (from template)")

    # Step 6: Download Isaac Sim (Animated Mockup)
    console.print(f"[bold blue]6. Dependencies:[/bold blue] Downloading Isaac Sim 5.1.0...")
    with Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        TaskProgressColumn(),
        "•",
        TextColumn("[bold cyan]{task.fields[speed]}")
    ) as progress:
        task = progress.add_task("download", filename="isaac-sim-5.1.0.zip", total=100, speed="0 MB/s")
        
        for i in range(101):
            time.sleep(0.05)
            speed = f"{i/10 + 20:.1f} MB/s"
            progress.update(task, completed=i, speed=speed)
            
    console.print(f"   [green]✔[/green] Extracting to {global_dir_name}/apps/5.1.0... (Simulated)")
    time.sleep(1)

    # Step 7: Optimization
    console.print(f"[bold blue]7. Optimization:[/bold blue] Applying Isaac Sim fixes...")
    with console.status("Patching isaacsim.asset.browser cache..."):
        time.sleep(1)
        console.print("   [green]✔[/green] Cache patched.")

    # Step 8: Finalizing
    console.print(f"[bold blue]8. Finalizing:[/bold blue] Generating configuration...")
    console.print("   [green]✔[/green] Created pow.toml (from template)")

    console.print(Panel(
        "[bold green]✨ Project initialized successfully! ✨[/bold green]",
        border_style="green"
    ))


@pow_group.command()
def run():
    """Run Isaac Sim or Isaac ROS workflows."""
    console.print(Panel("[bold green]Running workflow... (Mockup)[/bold green]", border_style="cyan"))


@pow_group.group()
def add():
    """Add resources to the project."""
    pass


@add.command()
@click.option("--isaac-sim", is_flag=True, default=True, help="Add Isaac Sim assets (default)")
@click.option("--all", is_flag=True, help="Add all available assets")
@click.option("--url", help="Asset URL to download")
@click.option("--path", help="Path to keep the asset")
def asset(isaac_sim, all, url, path):
    """Add assets to the project."""
    if url and path:
        console.print(f"   [cyan]➜[/cyan] Adding asset from [bold blue]{url}[/bold blue] to [bold magenta]{path}[/bold magenta]...")
    elif all:
        console.print("   [cyan]➜[/cyan] Adding [bold white]all[/bold white] available assets...")
    else:
        console.print("   [cyan]➜[/cyan] Adding [bold orange3]Isaac Sim[/bold orange3] assets...")
    
    with console.status("[bold green]Downloading and setting up assets..."):
        time.sleep(1.5)
        console.print("   [green]✔[/green] Assets added successfully.")


@pow_group.command()
@click.argument("file", type=click.Path(exists=True), required=False)
def lint(file):
    """Check .usda file for compatibility and errors."""
    if file:
        console.print(f"[bold blue]Linting[/bold blue] [white]{file}[/white]...")
    else:
        console.print("[bold blue]Linting[/bold blue] all [bold white].usda[/bold white] files...")
    
    with console.status("Checking for compatibility and errors..."):
        time.sleep(1)
        console.print("   [green]✔[/green] No errors found. Compatible with [bold]Isaac Sim 5.1.0[/bold].")
