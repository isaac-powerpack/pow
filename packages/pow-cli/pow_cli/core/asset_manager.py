from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import Config

class AssetManager:
    """Manages Isaac Sim and Omniverse assets."""

    def __init__(self, config: Config):
        self.config = config

    def ensure_global_assets(self) -> Path:
        """Ensure the global assets directory exists."""
        assets_path = self.config.global_path / "assets"
        assets_path.mkdir(parents=True, exist_ok=True)
        return assets_path

    def initialize_local_assets(self, target_folder_name: str) -> Dict[str, Any]:
        """
        Initialize local asset storage and link it to the global system.
        
        Args:
            target_folder_name: Name of the folder in the current project to store assets.
            
        Returns:
            Dictionary with paths and status information.
        """
        import tomlkit
        import os

        # 1. Determine local target path
        project_root = self.config.project_root or Path.cwd()
        local_assets_path = (project_root / target_folder_name).resolve()
        local_assets_path.mkdir(parents=True, exist_ok=True)

        # 2. Create assets_profile.toml in local folder
        profile_path = local_assets_path / "assets_profile.toml"
        if not profile_path.exists():
            doc = tomlkit.document()
            doc.add("project", project_root.name)
            doc.add("status", "initialized")
            doc.add("assets", tomlkit.array())
            with open(profile_path, "w") as f:
                f.write(tomlkit.dumps(doc))

        # 3. Create global symlink in ~/.pow/assets/
        global_assets_dir = self.ensure_global_assets()
        symlink_path = global_assets_dir / project_root.name
        
        # Remove existing symlink or file if it exists to avoid errors
        if symlink_path.exists() or symlink_path.is_symlink():
            if symlink_path.is_symlink():
                symlink_path.unlink()
            elif symlink_path.is_dir():
                import shutil
                shutil.rmtree(symlink_path)
            else:
                symlink_path.unlink()

        os.symlink(local_assets_path, symlink_path)

        # 4. Update assets_config.toml in .pow folder
        config_path = self.config.global_path / "assets_config.toml"
        if config_path.exists():
            with open(config_path, "r") as f:
                config_data = tomlkit.load(f)
        else:
            config_data = tomlkit.document()
            config_data.add("projects", tomlkit.table())

        projects = config_data.get("projects", tomlkit.table())
        projects[project_root.name] = {
            "path": str(local_assets_path),
            "initialized_at": os.path.getctime(local_assets_path)
        }
        config_data["projects"] = projects

        with open(config_path, "w") as f:
            f.write(tomlkit.dumps(config_data))

        return {
            "local_path": str(local_assets_path),
            "global_assets_path": str(global_assets_dir),
            "symlink_path": str(symlink_path),
            "config_file": str(config_path),
            "profile_file": str(profile_path)
        }

    def list_assets(self) -> List[Dict[str, Any]]:
        """
        Listing available assets and their status from the registry.
        """
        import tomllib
        from pathlib import Path

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
                    assets.append({
                        "name": pack.get("title", pack.get("name")),
                        "slug": pack.get("name"),
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
                        assets.append({
                            "name": pack.get("title", pack.get("name")),
                            "slug": pack.get("name"),
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