"""Manager core logic."""

from pathlib import Path
from ..common.utils import get_global_dir_name

class Manager:
    """Handles the management and initialization process for Isaac Powerpack."""

    def __init__(self):
        """Initialize the Manager with default paths."""
        self.global_dir_name = get_global_dir_name()
        self.home = Path.home()
        self.global_path = self.home / self.global_dir_name

    def get_config_info(self):
        """Return global configuration information for Step 1."""
        return {
            "global_dir_name": self.global_dir_name,
            "global_path": self.global_path
        }

    def create_global_folder(self):
        """Create the global directories and return the created paths with status."""
        subfolders = ["isaacsim", "modules", "projects", "sim-ros"]
        
        self.global_path.mkdir(parents=True, exist_ok=True)
        results = []
        for sub in subfolders:
            sub_path = self.global_path / sub
            existed = sub_path.exists()
            sub_path.mkdir(parents=True, exist_ok=True)
            results.append({
                "path": f"{self.global_dir_name}/{sub}",
                "status": "Existed" if existed else "Created"
            })
            
        return results

    def read_config(self):
        """Read configuration from an existing pow.toml file."""
        import tomllib
        pow_toml_path = Path("pow.toml")
        if pow_toml_path.exists():
            with open(pow_toml_path, "rb") as f:
                try:
                    self.config = tomllib.load(f)
                    return self.config
                except Exception as e:
                    print(f"Error reading pow.toml: {e}")
        return {}
