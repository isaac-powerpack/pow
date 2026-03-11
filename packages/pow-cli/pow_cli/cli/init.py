"""Init command implementation."""

import time
from pathlib import Path

import click
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.text import Text

from ..common.utils import console
from ..core.manager import Manager



# ── Logo ──────────────────────────────────────────────────────────────────────
def draw_logo():
# A brighter, punchier neon green
    NEON_GREEN = "#76ff7a" 
    
    # Refined font with better curves and proportions
    font = {
        'P': ["█████▄", "██▄▄██", "██▀▀▀ ", "██    "],
        'O': ["▄████▄", "██  ██", "██  ██", "▀████▀"],
        'W': ["██    ██", "██ ▄▄ ██", "████████", "▀██  ██▀"],
        'E': ["██████", "██▄▄▄ ", "██▀▀▀ ", "██████"],
        'R': ["█████▄", "██▄▄██", "██▀██ ", "██  ██"],
        'A': ["▄████▄", "██▄▄██", "██▀▀██", "██  ██"],
        'C': ["▄█████", "██    ", "██    ", "▀█████"],
        'K': ["██  ██", "██▄██ ", "██▀██ ", "██  ██"],
    }

    text = "POWERPACK"
    
    console.print("\n")
    
    # 1. Top UI framing line
    console.print("[dim white]" + "─" * 66 + "[/]\n")

    # 2. Perfectly Centered ISAAC Badge
    # (64 total width of text - 13 width of badge) / 2 = 25 spaces of padding
    console.print("                         [bold black on white]  I S A A C  [/]\n")

    # 3. The POWERPACK Text
    for i in range(4):
        line_content = ""
        for char in text:
            if char in font:
                # Add 1 space between each letter for breathability
                line_content += font[char][i] + " " 
        
        console.print(f"[{NEON_GREEN}]{line_content}[/]")

    # 4. Bottom UI framing and prompt
    console.print("\n[dim white]" + "─" * 66 + "[/]")

# ── Step helpers ──────────────────────────────────────────────────────────────

def _step1_check_config(global_dir_name: str) -> bool:
    """Print config header and verify pyproject.toml exists. Return False to abort."""
    if not Path("pyproject.toml").exists():
        console.print(
            "\n[bold red][1/8] ❌ Error:[/bold red] pyproject.toml not found. "
            "Please run this command in a valid project directory."
        )
        return False
    console.print(
        f"\n[bold blue][1/8] 🔧 Config:[/bold blue] "
        f"Using global directory [bold green]'{global_dir_name}'[/bold green]"
    )
    return True


def _step2_check_existing_config(manager: Manager) -> bool:
    """Ask whether to override an existing pow.toml. Returns override flag."""
    if not Path("pow.toml").exists():
        console.print(
            "[bold blue][2/8] 🔍 Check Existing Config [/bold blue] "
            "No existing pow.toml found. Proceeding..."
        )
        return True  # nothing to preserve, will create fresh

    console.print(
        "[bold blue][2/8] 🔍 Check Existing Config: [/bold blue] "
        "[yellow]Found existing pow.toml[/yellow]"
    )
    override = Confirm.ask(
        "   Do you want to override existing pow.toml?",
        default=False,
    )
    if override:
        console.print("   [green]Proceeding and will override pow.toml.[/green]")
    else:
        console.print("   [yellow]Proceeding with existing pow.toml.[/yellow]")
        manager.read_config()
        console.print("   [green]✔ Read existing pow.toml configuration.[/green]")
    return override


def _step3_global_folder(manager: Manager, global_path):
    """Create the .pow global folder and print the result."""
    console.print(
        f"[bold blue][3/8] 📂 Global Folder:[/bold blue] Preparing [dim]{global_path}[/dim]..."
    )
    init_data = manager.create_global_folder()

    if init_data["global_existed"]:
        console.print(
            f"   [yellow]✔[/yellow] Global directory [dim]{global_path}[/dim] already exists."
        )
    else:
        console.print(
            f"   [green]✔[/green] Global directory [dim]{global_path}[/dim] prepared successfully."
        )


def _step4_download_isaacsim(manager: Manager) -> dict | None:
    """Download Isaac Sim with a Rich progress bar. Returns result dict or None on error."""
    console.print("[bold blue][4/8] 📦 Isaac Sim App:[/bold blue] Installing Isaac Sim 5.1.0...")

    result = None
    error = None

    last_completed = 0
    last_time = time.time()
    current_phase = "download"

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

        def progress_callback(completed, total):
            nonlocal last_completed, last_time, current_phase
            if not total:
                return
            now = time.time()
            if current_phase == "download":
                progress.update(download_task, total=total, completed=completed)
                elapsed = now - last_time
                if elapsed >= 0.5:
                    speed_mb = ((completed - last_completed) / (1024 * 1024)) / elapsed
                    progress.update(download_task, speed=f"{speed_mb:.1f} MB/s")
                    last_completed = completed
                    last_time = now
            elif current_phase == "extract":
                progress.update(extract_task, total=total, completed=completed)

        def status_callback(status):
            nonlocal current_phase, last_completed, last_time
            if status == "Downloading":
                current_phase = "download"
            elif status == "Extracting":
                current_phase = "extract"
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
            elif status == "Extracted":
                progress.update(
                    extract_task,
                    filename="isaac-sim-5.1.0 [green](Extracted → 5.1.0)[/green]",
                )
                time.sleep(1)

        try:
            result = manager.download_isaacsim(
                progress_callback=progress_callback,
                status_callback=status_callback,
            )
        except Exception as e:
            error = e

    # Print outside the progress context so lines don't get consumed
    if error:
        console.print(f"   [bold red]❌ Error:[/bold red] {error}")
        return None
    if result["status"] == "Already installed":
        console.print(
            f"   [yellow]✔[/yellow] Isaac Sim 5.1.0 is already installed at [dim]{result['path']}[/dim]"
        )
    else:
        console.print(
            f"   [green]✔[/green] Downloaded and extracted to [dim]{result['path']}[/dim]"
        )
    return result


def _step5_optimization(manager: Manager, isaacsim_path: str):
    """Apply Isaac Sim post-install fixes."""
    console.print("[bold blue][5/8] ⚡ Optimization:[/bold blue] Applying Isaac Sim fixes...")
    with console.status("Fixing isaacsim.asset.browser cache file missing..."):
        fixed = manager.fix_asset_browser_cache(isaacsim_path)
    if fixed:
        console.print("   [green]✔[/green] Created missing cache file.")
    else:
        console.print("   [yellow]✔[/yellow] Cache file already exists.")


def _step6_ros_integration(manager: Manager, global_dir_name: str, forced_value: bool | None = None) -> bool:
    """Prompt for ROS integration and set it up. Returns whether ROS was enabled."""
    console.print("[bold blue][6/8] 🤖 ROS Integration:[/bold blue]")
    
    if forced_value is not None:
        enabled = forced_value
        status_text = "[bold green]enabled[/bold green]" if enabled else "[bold yellow]disabled[/bold yellow]"
        console.print(f"   Using existing ROS setting from pow.toml: {status_text}")
    else:
        enabled = Confirm.ask("   Enable ROS integration?", default=True)

    if not enabled:
        console.print("   [yellow]⊖[/yellow] Skipping ROS integration.")
        return False

    ros_cloned = False
    ros_already_built = False

    def ros_status_callback(state):
        nonlocal ros_cloned, ros_already_built
        if state == "cloning":
            ros_cloned = True
            status.update("[bold green]Cloning Isaac ROS workspace...")
        elif state == "existed":
            status.update("[bold yellow]Isaac ROS workspace already exists. Checking build...")
        elif state == "built":
            ros_already_built = True
            status.update("[bold yellow]Docker build already complete.")
        elif state == "building":
            status.update("[bold green]Docker build: Isaac ROS workspace...")
        elif state.startswith("building:"):
            line = state[len("building:"):]
            status.update(f"[bold green]Docker build:[/bold green] [dim]{line[:80]}[/dim]")

    with console.status("Preparing ROS workspace...") as status:
        try:
            ros_res = manager.setup_ros_workspace(status_callback=ros_status_callback)
        except Exception as e:
            console.print(f"   [bold red]❌ ROS Setup Error:[/bold red] {e}")
            return True  # user chose ROS, even if it failed

    clone_label = global_dir_name + "/sim-ros/IsaacSim-ros_workspaces"
    if ros_cloned:
        console.print(f"   [green]✔[/green] Cloned IsaacSim-ros_workspaces to [dim]{clone_label}[/dim]")
    else:
        console.print(f"   [yellow]✔[/yellow] IsaacSim-ros_workspaces already available in [dim]{clone_label}[/dim]")

    distro_label = f"ROS [bold]{ros_res['ros_distro']}[/bold] (Ubuntu {ros_res['ubuntu_version']})"
    if ros_already_built:
        console.print(f"   [yellow]✔[/yellow] Docker build already complete for {distro_label}.")
    else:
        console.print(f"   [green]✔[/green] Docker build complete for {distro_label}.")

    return True


def _step7_project_structure(manager: Manager):
    """Create local project folders and .gitignore."""
    console.print("[bold blue][7/8] 🏗️ Project Structure:[/bold blue] Creating local folders...")
    local_folders = ["exts", "scripts", ".modules", ".assets", "standalone"]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(
            description="Setting up project folders...", total=len(local_folders) + 1
        )
        struct_data = manager.setup_project_structure(local_folders)
        for res in struct_data["results"]:
            progress.update(task, advance=1, description=f"Setting up {res['path']}...")
            time.sleep(0.1)

    console.print("   [green]✔[/green] Local folders created.")

    gitignore_res = next((r for r in struct_data["results"] if r["path"] == ".gitignore"), None)
    if gitignore_res and gitignore_res["status"] == "Created from template":
        console.print("   [green]✔[/green] Created .gitignore (from template)")
    elif gitignore_res and gitignore_res["status"] == "Template not found":
        console.print("   [yellow]⚠[/yellow] .gitignore template not found. [dim]Skipped.[/dim]")
    else:
        console.print("   [yellow]✔[/yellow] .gitignore already exists. [dim]Kept existing.[/dim]")


def _step8_finalize(manager: Manager, override_pow_toml: bool, ros_enabled: bool):
    """Generate pow.toml configuration."""
    console.print("[bold blue][8/8] ✅ Finalizing:[/bold blue] Generating configuration...")
    result = manager.create_pow_toml(override=override_pow_toml, enable_ros=ros_enabled)
    if result["status"] == "Created":
        console.print("   [green]✔[/green] Created pow.toml (from template)")
    elif result["status"] == "Existed":
        console.print("   [yellow]✔[/yellow] Kept existing pow.toml")
    else:
        console.print("   [yellow]⚠[/yellow] pow.toml template not found. [dim]Skipped.[/dim]")


# ── Command entry point ───────────────────────────────────────────────────────

@click.command(name="init")
def init_cmd():
    """Initialize Isaac ROS project (Mockup with Rich)."""
    manager = Manager()
    config = manager.get_config_path()
    global_dir_name = config["global_dir_name"]
    global_path = config["global_path"]

    draw_logo()

    console.print(
            "\n"
            "[bold cyan]🚀 Initialization Pow Project[/bold cyan]",
    )

    if not _step1_check_config(global_dir_name):
        return

    override_pow_toml = _step2_check_existing_config(manager)
    _step3_global_folder(manager, global_path)

    download_result = _step4_download_isaacsim(manager)
    if download_result is None:
        return

    _step5_optimization(manager, download_result["path"])
    
    # Use existing ROS setting if not overriding pow.toml
    ros_forced = None
    if not override_pow_toml:
        try:
            ros_forced = manager.config.get("enable_ros", False)
        except Exception:
            pass

    ros_enabled = _step6_ros_integration(manager, global_dir_name, forced_value=ros_forced)
    _step7_project_structure(manager)
    
    if override_pow_toml:
        _step8_finalize(manager, override_pow_toml, ros_enabled)
    else:
        console.print("[bold blue][8/8] ✅ Finalizing:[/bold blue] [yellow]Kept existing pow.toml[/yellow]")

    console.print(
        Panel(
            "[bold green]✨ Project initialized successfully! ✨[/bold green]",
            border_style="green",
        )
    )
