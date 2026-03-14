"""Asset command implementation."""

import click
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


