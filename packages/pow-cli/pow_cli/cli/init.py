"""Init command implementation."""

import time
from pathlib import Path

import click
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.prompt import Confirm
from rich.table import Table

from ..common.utils import console
from ..core.manager import Manager


@click.command(name="init")
def init_cmd():
    """Initialize Isaac ROS project (Mockup with Rich)."""
    manager = Manager()
    config = manager.get_config_info()
    global_dir_name = config["global_dir_name"]
    global_path = config["global_path"]

    console.print(
        Panel.fit(
            "[bold cyan]🚀 Isaac Powerpack Initialization[/bold cyan]",
            subtitle="[dim]Setting up your Isaac Sim environment[/dim]",
        )
    )

    # Step 1: Pow.toml Check
    override_pow_toml = True
    if Path("pow.toml").exists():
        console.print(
            f"\n[bold blue][1/8] 🔍 Check Existing Config: [/bold blue] [yellow]Found existing pow.toml[/yellow]"
        )
        override_pow_toml = Confirm.ask(
            "   Do you want to override existing pow.toml and re-initialize?",
            default=False,
        )
        if not override_pow_toml:
            console.print("   [yellow]Proceeding with existing pow.toml.[/yellow]")
            manager.read_config()
            console.print("   [green]✔ Read existing pow.toml configuration.[/green]")
        else:
            console.print("   [green]Proceeding and will override pow.toml.[/green]")
    else:
        console.print(
            f"\n[bold blue][1/8] 🔍 Check Existing Config [/bold blue] No existing pow.toml found. Proceeding..."
        )

    # Step 2: Display global dir name
    console.print(
        f"[bold blue][2/8] 🔧 Config:[/bold blue] Using global directory [bold green]'{global_dir_name}'[/bold green]"
    )

    # Step 3: Global Folder
    console.print(
        f"[bold blue][3/8] 📂 Global Folder:[/bold blue] Preparing [dim]{global_path}[/dim]..."
    )
    results = manager.create_global_folder()
    table = Table(show_header=False, box=None, padding=(0, 2))
    for res in results:
        status_color = "green" if res["status"] == "Created" else "yellow"
        table.add_row(f"[{status_color}]✔[/{status_color}] {res['status']}", res["path"])
    console.print(table)

    # Step 4: Isaac Sim App (Animated Mockup)
    console.print(f"[bold blue][4/8] 📦 Isaac Sim App:[/bold blue] Downloading Isaac Sim 5.1.0...")
    with Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        TaskProgressColumn(),
        "•",
        TextColumn("[bold cyan]{task.fields[speed]}"),
    ) as progress:
        task = progress.add_task(
            "download", filename="isaac-sim-5.1.0.zip", total=100, speed="0 MB/s"
        )

        for i in range(101):
            time.sleep(0.05)
            speed = f"{i/10 + 20:.1f} MB/s"
            progress.update(task, completed=i, speed=speed)

    console.print(
        f"   [green]✔[/green] Extracting to {global_dir_name}/isaacsim/5.1.0... (Simulated)"
    )
    time.sleep(1)

    # Step 5: Optimization
    console.print(
        f"[bold blue][5/8] ⚡ Optimization:[/bold blue] Applying Isaac Sim fixes..."
    )
    with console.status("Patching isaacsim.asset.browser cache..."):
        time.sleep(1)
        console.print("   [green]✔[/green] Cache patched.")

    # Step 6: ROS Integration
    console.print(f"[bold blue][6/8] 🤖 ROS Integration:[/bold blue]")
    if Confirm.ask("   Enable ROS integration?", default=True):
        with console.status("[bold green]Cloning Isaac ROS workspace..."):
            time.sleep(1.5)  # Simulated delay
            console.print(
                f"   [green]✔[/green] Cloned IsaacSim-ros_workspaces to {global_dir_name}/sim-ros"
            )

        with console.status("[bold green]Building Isaac ROS workspace in Docker..."):
            time.sleep(2)  # Simulated delay
            console.print("   [green]✔[/green] Build complete.")

    # Step 7: Project Structure
    console.print(
        f"[bold blue][7/8] 🏗️ Project Structure:[/bold blue] Creating local folders..."
    )
    local_folders = ["exts", "scripts", ".modules", ".assets", "standalone"]
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(
            description="Setting up project folders...", total=len(local_folders)
        )
        for folder in local_folders:
            time.sleep(0.3)
            progress.update(task, advance=1, description=f"Created ./{folder}")

    console.print("   [green]✔[/green] Local folders created.")
    console.print("   [green]✔[/green] Created .gitignore (from template)")

    # Step 8: Finalizing
    console.print(f"[bold blue][8/8] ✅ Finalizing:[/bold blue] Generating configuration...")
    if override_pow_toml:
        console.print("   [green]✔[/green] Created pow.toml (from template)")
    else:
        console.print("   [green]✔[/green] Kept existing pow.toml")

    console.print(
        Panel(
            "[bold green]✨ Project initialized successfully! ✨[/bold green]",
            border_style="green",
        )
    )

