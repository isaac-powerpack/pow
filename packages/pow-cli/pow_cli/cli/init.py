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
            subtitle="[dim]Setting up Isaac Sim environment[/dim]",
        )
    )

    # Step 1: Config
    if not Path("pyproject.toml").exists():
        console.print(
            "\n[bold red][1/8] ❌ Error:[/bold red] pyproject.toml not found. Please run this command in a valid project directory."
        )
        return

    console.print(
        f"\n[bold blue][1/8] 🔧 Config:[/bold blue] Using global directory [bold green]'{global_dir_name}'[/bold green]"
    )

    # Step 2: Pow.toml Check
    override_pow_toml = True
    if Path("pow.toml").exists():
        console.print(
            "[bold blue][2/8] 🔍 Check Existing Config: [/bold blue] [yellow]Found existing pow.toml[/yellow]"
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
            "[bold blue][2/8] 🔍 Check Existing Config [/bold blue] No existing pow.toml found. Proceeding..."
        )

    # Step 3: Global Folder
    console.print(
        f"[bold blue][3/8] 📂 Global Folder:[/bold blue] Preparing [dim]{global_path}[/dim]..."
    )
    init_data = manager.create_global_folder()
    
    if init_data["global_existed"]:
        console.print(f"   [yellow]✔[/yellow] Global directory [dim]{global_path}[/dim] already exists. [dim]Skipping global folder creation.[/dim]")
    else:
        table = Table(show_header=False, box=None, padding=(0, 2))
        for res in init_data["results"]:
            if res["status"] == "Created":
                status_str = "[green]✔ Created[/green]"
            elif res["status"] == "Existed":
                status_str = "[yellow]✔ Existed[/yellow]"
            else:  # Skipped
                status_str = "[dim blue]⊖ Skipped[/dim blue]"
            table.add_row(status_str, res["path"])
        console.print(table)

    # Step 4: Isaac Sim App
    console.print(f"[bold blue][4/8] 📦 Isaac Sim App:[/bold blue] Downloading Isaac Sim 5.1.0...")
    _download_result = None
    _download_error = None

    with Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=40),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        TextColumn("[bold cyan]{task.fields[speed]}"),
        console=console,
        refresh_per_second=10,
    ) as progress:
        download_task = progress.add_task(
            "download", filename="isaac-sim-5.1.0.zip", total=None, speed="0 MB/s"
        )
        extract_task = progress.add_task(
            "extract", filename="", total=None, speed=" ", visible=False
        )

        last_completed = 0
        last_time = time.time()
        last_update_time = 0.0
        current_phase = "download"

        def progress_callback(completed, total):
            nonlocal last_completed, last_time, last_update_time
            if not total:
                return

            current_time = time.time()
            last_update_time = current_time

            if current_phase == "download":
                progress.update(download_task, total=total, completed=completed)
                # Calculate download speed
                elapsed = current_time - last_time
                if elapsed >= 0.5:
                    downloaded_since_last = completed - last_completed
                    speed_mb = (downloaded_since_last / (1024 * 1024)) / elapsed
                    progress.update(download_task, speed=f"{speed_mb:.1f} MB/s")
                    last_completed = completed
                    last_time = current_time
            elif current_phase == "extract":
                progress.update(extract_task, total=total, completed=completed)

        def status_callback(status):
            nonlocal current_phase, last_completed, last_time, last_update_time
            if status == "Downloading":
                current_phase = "download"
            elif status == "Extracting":
                current_phase = "extract"
                # Hide download task, show extract task
                progress.update(download_task, visible=False)
                progress.update(
                    extract_task,
                    filename="isaac-sim-5.1.0 [yellow](Extracting...)[/yellow]",
                    speed=" ",
                    completed=0,
                    total=None,
                    visible=True,
                )
                last_completed = 0
                last_time = time.time()
                last_update_time = 0.0
            elif status == "Extracted":
                progress.update(
                    extract_task,
                    filename="isaac-sim-5.1.0 [green](Extracted → 5.1.0)[/green]",
                )
                time.sleep(1)

        try:
            _download_result = manager.download_isaacsim(
                progress_callback=progress_callback,
                status_callback=status_callback
            )
        except Exception as e:
            _download_error = e

    # Print result/error AFTER Progress context has closed
    if _download_error:
        console.print(f"   [bold red]❌ Error:[/bold red] {_download_error}")
        return
    elif _download_result["status"] == "Already installed":
        console.print(f"   [yellow]✔[/yellow] Isaac Sim 5.1.0 is already installed at [dim]{_download_result['path']}[/dim]")
    else:
        console.print(f"   [green]✔[/green] Downloaded and extracted to [dim]{_download_result['path']}[/dim]")


    # Step 5: Optimization
    console.print(
        f"[bold blue][5/8] ⚡ Optimization:[/bold blue] Applying Isaac Sim fixes..."
    )
    with console.status("Fixing isaacsim.asset.browser cache file missing..."):
        fixed = manager.fix_asset_browser_cache(_download_result["path"])
        if fixed:
            console.print("   [green]✔[/green] Created missing cache file.")
        else:
            console.print("   [yellow]✔[/yellow] Cache file already exists.")

    # Step 6: ROS Integration
    console.print(f"[bold blue][6/8] 🤖 ROS Integration:[/bold blue]")
    if Confirm.ask("   Enable ROS integration?", default=True):
        
        status_msg = "Preparing ROS workspace..."
        _ros_cloned = False
        _ros_already_built = False
        with console.status(status_msg) as status:
            def ros_status_callback(state):
                nonlocal _ros_cloned, _ros_already_built
                if state == "cloning":
                    _ros_cloned = True
                    status.update("[bold green]Cloning Isaac ROS workspace...")
                elif state == "existed":
                    status.update("[bold yellow]Isaac ROS workspace already exists. Checking build...")
                elif state == "built":
                    _ros_already_built = True
                    status.update("[bold yellow]Docker build already complete.")
                elif state == "building":
                    status.update("[bold green]Docker build: Isaac ROS workspace...")
                elif state.startswith("building:"):
                    line = state[len("building:"):]
                    status.update(f"[bold green]Docker build:[/bold green] [dim]{line[:80]}[/dim]")
            
            try:
                ros_res = manager.setup_ros_workspace(status_callback=ros_status_callback)
                
                # Report outcomes
                if _ros_cloned:
                     console.print(f"   [green]✔[/green] Cloned IsaacSim-ros_workspaces to [dim]{global_dir_name}/sim-ros/IsaacSim-ros_workspaces[/dim]")
                else:
                     console.print(f"   [yellow]✔[/yellow] IsaacSim-ros_workspaces already available in [dim]{global_dir_name}/sim-ros/IsaacSim-ros_workspaces[/dim]")
                
                if _ros_already_built:
                     console.print(f"   [yellow]✔[/yellow] Docker build already complete for ROS [bold]{ros_res['ros_distro']}[/bold] (Ubuntu {ros_res['ubuntu_version']}).")
                else:
                     console.print(f"   [green]✔[/green] Docker build complete for ROS [bold]{ros_res['ros_distro']}[/bold] (Ubuntu {ros_res['ubuntu_version']}).")
                
            except Exception as e:
                console.print(f"   [bold red]❌ ROS Setup Error:[/bold red] {e}")
    else:
        console.print("   [yellow]⊖[/yellow] Skipping ROS integration.")

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
            description="Setting up project folders...", total=len(local_folders) + 1
        )
        
        # Real structure setup
        struct_data = manager.setup_project_structure(local_folders)
        
        for res in struct_data["results"]:
            progress.update(task, advance=1, description=f"Setting up {res['path']}...")
            time.sleep(0.1) # Brief delay for visibility in mockup feel
            
    # Success feedback
    console.print("   [green]✔[/green] Local folders created.")
    
    gitignore_res = next((r for r in struct_data["results"] if r["path"] == ".gitignore"), None)
    if gitignore_res and gitignore_res["status"] == "Created from template":
        console.print("   [green]✔[/green] Created .gitignore (from template)")
    elif gitignore_res and gitignore_res["status"] == "Template not found":
        console.print("   [yellow]⚠[/yellow] .gitignore template not found. [dim]Skipped.[/dim]")
    else:
        console.print("   [yellow]✔[/yellow] .gitignore already exists. [dim]Kept existing.[/dim]")

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

