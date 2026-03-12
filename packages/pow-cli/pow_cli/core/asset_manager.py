from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import Config

class AssetManager:
    """Manages Isaac Sim and Omniverse assets."""

    def __init__(self, config: Config):
        self.config = config

    def init(self) -> Dict[str, Any]:
        """
        Mock initialization of asset directory and tracking.
        Returns a dictionary with status information.
        """
        return {
            "assets_path": str(self.config.global_path / "assets"),
            "tracking_file": str(self.config.global_path / "assets" / "tracking.json"),
            "mapping": {"isaac-sim": "5.1.0"},
            "symlink": ".pow/assets"
        }

    def list_assets(self) -> List[Dict[str, Any]]:
        """
        Listing available assets and their status from the registry.
        """
        import tomllib
        import os

        # Get path to the data directory relative to this file
        data_dir = Path(__file__).parent.parent / "data" / "asset-registry"
        
        assets = []

        # 1. Load Isaac Sim assets (Individual packs)
        isaac_path = data_dir / "isaacsim_assets_5_1_0.toml"
        if isaac_path.exists():
            with open(isaac_path, "rb") as f:
                data = tomllib.load(f)
                isaac_data = data.get("isaac_sim_assets", {})
                version = isaac_data.get("version", "5.1.0")
                for pack in isaac_data.get("packs", []):
                    assets.append({
                        "name": pack["name"],
                        "group": f"isaac-sim {version}",
                        "status": "Not Loaded",
                        "completion": 0,
                        "size": pack.get("size", "N/A")
                    })

        # 2. Load Omniverse assets
        omni_path = data_dir / "omniverse_assets.toml"
        if omni_path.exists():
            with open(omni_path, "rb") as f:
                data = tomllib.load(f)
                
                group_mapping = {
                    "3d_assets": "omniverse / 3d_assets",
                    "sim_ready": "omniverse / sim-ready",
                    "materials": "omniverse / material",
                    "environments": "omniverse / environments",
                    "workflows": "omniverse / workflow"
                }

                omni_data = data.get("omniverse", {})
                for key, group_name in group_mapping.items():
                    for pack in omni_data.get(key, []):
                        assets.append({
                            "name": pack["name"],
                            "group": group_name,
                            "status": "Not Loaded",
                            "completion": 0,
                            "size": pack.get("size", "N/A")
                        })

        return assets

    def add_asset(self, name: str, keep_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Mock adding an asset (download and extraction).
        """
        # Simulate check if already installed
        if name == "isaac-sim-5.1.0":
            return {"status": "already_installed", "message": f"Asset '{name}' is already installed."}

        return {
            "status": "success",
            "name": name,
            "path": keep_path or str(Path.home() / "Downloads"),
            "extracted_to": str(self.config.global_path / "assets" / name)
        }