"""Core logic for Isaac Sim asset management."""

import subprocess
from pathlib import Path


def get_isaacsim_kit_path() -> Path | None:
    """Get the path to isaacsim.exp.base.kit file."""
    try:
        import isaacsim
        return Path(isaacsim.__file__).parent / "apps" / "isaacsim.exp.base.kit"
    except ImportError:
        return None


def generate_settings_block(asset_base: Path) -> str:
    """Generate the settings block to add to the kit file."""
    return f'''
# Local asset settings (added by pow cli)
[settings]
exts."isaacsim.asset.browser".visible_after_startup = true
persistent.isaac.asset_root.default = "{asset_base}"
# End: Local asset settings (added by pow cli)
'''


def update_kit_settings(asset_root: Path, version: str = "5.1.0") -> Path:
    """Update the isaacsim.exp.base.kit file with local asset paths."""
    kit_path = get_isaacsim_kit_path()
    if not kit_path or not kit_path.exists():
        raise FileNotFoundError("Could not find kit file.")

    version_short = ".".join(version.split(".")[:2])
    asset_base = asset_root / "Assets" / "Isaac" / version_short
    settings_block = generate_settings_block(asset_base)

    content = kit_path.read_text()
    if "# Local asset settings" in content:
        # Replacement logic would go here
        pass

    with open(kit_path, "w") as f:
        f.write(content + settings_block)

    return asset_base


def download_assets(target_path: Path, version: str = "5.1.0") -> None:
    """Download Isaac Sim asset zip parts."""
    subprocess.run(["aria2c", f"https://.../assets-{version}.zip", "-d", str(target_path)], check=True)


def extract_assets(target_path: Path, version: str = "5.1.0", keep_zip: bool = False) -> None:
    """Merge and extract Isaac Sim asset zip files."""
    subprocess.run(["unzip", str(target_path / "assets.zip"), "-d", str(target_path / "isaacsim_assets")], check=True)
