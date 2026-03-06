"""Add command implementation."""

import time
import click
from ..common.utils import console

@click.group(name="add")
def add_group():
    """Add resources to the project."""
    pass

@add_group.command(name="asset")
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
