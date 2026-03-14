from typing import List, Dict, Any
from pathlib import Path
from .models.pow_config import PowConfig

class AssetManager:
    """Manages Isaac Sim and Omniverse assets."""

    def __init__(self, config: PowConfig):
        self.config = config

    def _parse_size(self, size_str: str) -> float:
        """Parse size string like '2.62 GB' or '891MB' into GB float."""
        if not size_str or size_str == "N/A":
            return 0.0
        
        size_str = size_str.upper().replace(" ", "")
        try:
            if "GB" in size_str:
                return float(size_str.replace("GB", ""))
            elif "MB" in size_str:
                return float(size_str.replace("MB", "")) / 1024.0
            return float(size_str)
        except ValueError:
            return 0.0

    def get_asset_status(self, slug: str) -> Dict[str, Any]:
        """
        Check the status of a specific asset from local tracking.
        Returns mock status for now.
        """
        # Mock status check logic
        if slug == "robots_and_sensors":
            return {"status": "Installed", "percent": 100}
        return {"status": "Not Loaded", "percent": 0}

    def list_assets(self) -> List[Dict[str, Any]]:
        """
        Listing available assets and their status from the registry.
        """
        import tomllib

        # Get path to the data directory relative to this file
        data_dir = Path(__file__).parent.parent / "data" / "asset-registry"
        
        assets = []

        # 1. Load Isaac Sim assets
        isaac_path = data_dir / "isaacsim_assets_5_1_0.toml"
        if isaac_path.exists():
            with open(isaac_path, "rb") as f:
                data = tomllib.load(f)
                isaac_root = data.get("isaacsim_assets", {})
                version = isaac_root.get("version", "5.1.0")
                
                # In the new structure, assets are under isaacsim_assets.isaacsim_5_1_0
                packs = isaac_root.get("isaacsim_5_1_0", [])
                for pack in packs:
                    slug = pack.get("name")
                    status_info = self.get_asset_status(slug)
                    assets.append({
                        "name": pack.get("title", pack.get("name")),
                        "slug": slug,
                        "group": f"isaac-sim {version}",
                        "category": "isaacsim_5_1_0",
                        "status": status_info["status"],
                        "completion": status_info["percent"],
                        "size": pack.get("size", "N/A")
                    })

        # 2. Load Omniverse assets
        omni_path = data_dir / "omniverse_assets.toml"
        if omni_path.exists():
            with open(omni_path, "rb") as f:
                data = tomllib.load(f)
                
                group_mapping = {
                    "omni_3d_assets": "omniverse / 3d_assets",
                    "omni_sim_ready": "omniverse / sim-ready",
                    "omni_materials": "omniverse / material",
                    "omni_environments": "omniverse / environments",
                    "omni_workflows": "omniverse / workflow"
                }

                omni_root = data.get("omniverse", {})
                for key, group_name in group_mapping.items():
                    packs = omni_root.get(key, [])
                    for pack in packs:
                        slug = pack.get("name")
                        status_info = self.get_asset_status(slug)
                        assets.append({
                            "name": pack.get("title", pack.get("name")),
                            "slug": slug,
                            "group": group_name,
                            "category": key,
                            "status": status_info["status"],
                            "completion": status_info["percent"],
                            "size": pack.get("size", "N/A")
                        })

        return assets