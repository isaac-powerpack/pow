"""Shared Isaac Sim installation progress for init and sim commands."""

import time

from rich.progress import BarColumn, Progress, TextColumn

from .utils import console
from ..core.initializer import Initializer


def download_with_progress(
    initializer: Initializer, version: str, *, check: bool = False
) -> dict:
    """Install an already-selected version, propagating setup failures."""
    console.print(f"   Installing Isaac Sim [bold]{version}[/bold]...")

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
            "download", filename=f"isaac-sim-{version}.zip", total=None, speed="0 MB/s"
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
                    filename=f"isaac-sim-{version} [yellow](Extracting...)[/yellow]",
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
                    filename=f"isaac-sim-{version} [green](Extracted → {version})[/green]",
                )
                time.sleep(1)

        result = initializer.download_isaacsim(
            version=version,
            progress_callback=progress_callback,
            status_callback=status_callback,
            check=check,
        )

    # Print outside the progress context so lines don't get consumed.
    result.setdefault("version", version)
    if result["status"] == "Already installed":
        console.print(
            f"   [yellow]✔[/yellow] Isaac Sim {version} is already installed at [dim]{result['path']}[/dim]"
        )
    else:
        console.print(
            f"   [green]✔[/green] Downloaded and extracted to [dim]{result['path']}[/dim]"
        )
    if result.get("backup"):
        console.print(f"   Previous installation preserved at [dim]{result['backup']}[/dim]")
    return result

