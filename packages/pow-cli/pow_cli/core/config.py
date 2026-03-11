import tomllib
from pathlib import Path
from typing import Any, Optional


class Config:
    """Singleton class to read and provide access to pow.toml."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        self._project_root = self._find_project_root()
        self._data: dict[str, Any] = {}

        if self._project_root:
            self._load_config(self._project_root)

    def _find_project_root(self, start_path: Optional[Path] = None) -> Optional[Path]:
        """Find the project root by locating pow.toml."""
        if start_path is None:
            start_path = Path.cwd()

        current = start_path.resolve()

        while current != current.parent:
            if (current / "pow.toml").exists():
                return current
            current = current.parent

        if (current / "pow.toml").exists():
            return current

        return None

    def _load_config(self, project_root: Path) -> None:
        """Load pow.toml configuration into memory."""
        config_path = project_root / "pow.toml"
        if not config_path.exists():
            return

        with open(config_path, "rb") as f:
            self._data = tomllib.load(f)

    @property
    def project_root(self) -> Optional[Path]:
        """Get the project root directory."""
        return self._project_root

    @property
    def data(self) -> dict[str, Any]:
        """Get the complete parsed data from pow.toml."""
        return self._data

    def get_profile(self, profile_name: str = "default") -> dict[str, Any]:
        """
        Get a merged profile dictionary.
        
        If profile_name is 'default' or 'sim', it returns data from [sim] only.
        Otherwise, it merges [sim] with the requested profile from the top-level 'profiles' list.
        """
        sim_data = self._data.get("sim", {}).copy()

        if profile_name in ("default", "sim"):
            return sim_data

        profiles = self._data.get("profiles", [])
        
        # Merge with target profile entry in [[profiles]]
        target_profile = next((p for p in profiles if p.get("name") == profile_name), None)
        if target_profile:
            sim_data.update({k: v for k, v in target_profile.items() if k != "name"})
            
        return sim_data

    def get(self, key: str, default: Any = None, profile: str = "default") -> Any:
        """
        Get a specific setting from pow.toml, defaulting to the '[sim]' profile.
        
        Args:
            key: The setting key to fetch.
            default: The default value if the key does not exist.
            profile: The profile name to look in, defaults to 'default' (which maps to [sim]).
        """
        profile_data = self.get_profile(profile)
        return profile_data.get(key, default)
