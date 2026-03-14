"""Asset command implementation."""

import click
from pathlib import Path
from rich.panel import Panel
from rich.table import Table

from ..common.utils import console
from ..core.models.pow_config import PowConfig
from ..core.asset_manager import AssetManager


@click.group(name="asset")
def asset_group():
    """Manage Isaac Sim and Omniverse assets."""
    pass



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


@asset_group.command(name="attach")
@click.argument("path", required=True)
def asset_attach(path):
    """Attach a local folder as an asset source for Isaac Sim/Omniverse."""
    config = PowConfig()
    global_path = config.global_path
    system_toml_path = global_path / "system.toml"
    asset_symlink_path = global_path / "assets"

    target_folder = Path(path).expanduser().resolve()
    console.print(f"\n[bold green]> Target Folder set to: [cyan]{target_folder}[/cyan][/bold green]")

    # =========================================================
    # Step 1: Pre-flight Checks
    # =========================================================
    console.print("[bold blue][1/5] Pre-flight Checks[/bold blue]")

    if asset_symlink_path.exists() or asset_symlink_path.is_symlink():
        console.print(f"   [red]✗[/red] Already attached at [dim]{asset_symlink_path}[/dim] — run [bold]pow asset detach[/bold] first.")
        return

    if system_toml_path.exists():
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            with open(system_toml_path, "rb") as f:
                system_data = tomllib.load(f)
            if system_data.get("asset", {}).get("use_local_asset", False):
                local_path = system_data.get("asset", {}).get("local_asset_path", "")
                console.print(f"   [red]✗[/red] Already configured at [dim]{local_path}[/dim] — run [bold]pow asset detach[/bold] first.")
                return
        except Exception:
            pass

    if not target_folder.exists() or not target_folder.is_dir():
        console.print(f"   [red]✗[/red] Invalid target folder: [dim]{target_folder}[/dim]")
        return

    system_toml_action = "create from template" if not system_toml_path.exists() else "already exists"
    console.print(f"   [green]✔[/green] No existing attachment · Target folder valid · system.toml {system_toml_action}")
    console.print(f"   [green]✔[/green] Would set [dim]use_local_asset = true[/dim], [dim]local_asset_path = \"{target_folder}\"[/dim]")

    # =========================================================
    # Step 2: Assets Folder
    # =========================================================
    console.print("\n[bold blue][2/5] Assets Folder[/bold blue]")
    action = "already exists" if asset_symlink_path.exists() else f"would create [dim]{asset_symlink_path}[/dim]"
    console.print(f"   [green]✔[/green] {action}")

    # =========================================================
    # Step 3: Symlink
    # =========================================================
    console.print("\n[bold blue][3/5] Symlink[/bold blue]")
    console.print(f"   [green]✔[/green] Would link [dim]{asset_symlink_path} → {target_folder}[/dim]")

    # =========================================================
    # Step 4: Asset Profile
    # =========================================================
    console.print("\n[bold blue][4/5] Asset Profile[/bold blue]")
    target_profile_path = target_folder / "asset-profile.toml"
    console.print(f"   [green]✔[/green] Would copy profile to [dim]{target_profile_path}[/dim]")

    # =========================================================
    # Step 5: Omniverse Aliases & Isaac Sim Config
    # =========================================================
    console.print("\n[bold blue][5/5] Omniverse Aliases & Isaac Sim Config[/bold blue]")
    omniverse_config_path = Path.home() / ".nvidia-omniverse" / "config" / "omniverse.toml"
    assets_abs_path = str(asset_symlink_path.resolve())
    isaacsim_version = config.ISAACSIM_VERSION
    isaacsim_kit_path = global_path / "isaacsim" / isaacsim_version / "apps" / "isaacsim.exp.base.kit"

    console.print(f"   [green]✔[/green] Would add 6 URL aliases → [dim]{assets_abs_path}[/dim] in [dim]{omniverse_config_path}[/dim]")
    console.print(f"   [green]✔[/green] Would enable asset browser in [dim]{isaacsim_kit_path}[/dim]")

    # =========================================================
    # Success panel
    # =========================================================
    console.print()
    console.print(
        Panel(
            f"[bold green]✔ Ready to attach[/bold green] [dim]{target_folder}[/dim]\n\n"
            "[dim]MOCKUP only — no changes were made.[/dim]",
            border_style="green",
        )
    )


