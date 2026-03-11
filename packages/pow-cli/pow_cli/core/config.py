import tomllib
from pathlib import Path
from typing import Any, Optional

class Config:
    """Singleton class that provides project-wide configuration.

    Responsibilities:
    - Isaac Sim / ROS constants (class-level).
    - Global directory paths (home, global_path) – always available.
    - pow.toml project settings – available only when a pow.toml is found.
    """

    _instance = None

    # ── Isaac Sim constants ───────────────────────────────────────────────────

    ISAACSIM_VERSION = "5.1.0"
    ISAACSIM_FILENAME = f"isaac-sim-standalone-{ISAACSIM_VERSION}-linux-x86_64.zip"
    ISAACSIM_URL = f"https://download.isaacsim.omniverse.nvidia.com/{ISAACSIM_FILENAME}"
    SUPPORTED_UBUNTU_VERSIONS = ["22.04", "24.04"]

    # ── ROS constants ────────────────────────────────────────────────────────

    ROS_DISTRO_MAP: dict[str, str] = {"24.04": "jazzy", "22.04": "humble"}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        # ── Global / home paths (always available) ────────────────────────────
        self._global_dir_name: str = self._read_global_dir_name()
        self._home: Path = Path.home()
        self._global_path: Path = self._home / self._global_dir_name

        # ── Project config (requires pow.toml) ───────────────────────────────
        self._project_root: Optional[Path] = self._find_project_root()
        self._data: dict[str, Any] = {}

        if self._project_root:
            self._load_config(self._project_root)

    @staticmethod
    def _read_global_dir_name() -> str:
        """Read global_dir_name from pyproject.toml or default to .pow"""
        pyproject_path = Path.cwd() / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                try:
                    data = tomllib.load(f)
                    val = data.get("tool", {}).get("pow-cli", {}).get("global_dir_name")
                    if val:
                        return val
                except Exception:
                    pass
        return ".pow"

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

    # ── Global / home path properties ────────────────────────────────────────

    @property
    def global_dir_name(self) -> str:
        """The name of the global pow directory (e.g. '.pow')."""
        return self._global_dir_name

    @property
    def home(self) -> Path:
        """The current user's home directory."""
        return self._home

    @property
    def global_path(self) -> Path:
        """Absolute path to the global pow directory (e.g. ~/.pow)."""
        return self._global_path

    # ── Project config properties ────────────────────────────────────────────

    @property
    def project_root(self) -> Optional[Path]:
        """Get the project root directory, or None if pow.toml was not found."""
        return self._project_root

    @property
    def data(self) -> dict[str, Any]:
        """Get the complete parsed data from pow.toml.

        Raises RuntimeError if pow.toml was not found during initialization.
        """
        self._require_project()
        return self._data

    def get_profile(self, profile_name: str = "default") -> dict[str, Any]:
        """
        Get a merged profile dictionary.

        If profile_name is 'default' or 'sim', it returns data from [sim] only.
        Otherwise, it merges [sim] with the requested profile from the top-level
        'profiles' list.

        Raises RuntimeError if pow.toml was not found.
        """
        self._require_project()
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

        Raises RuntimeError if pow.toml was not found.
        """
        profile_data = self.get_profile(profile)
        return profile_data.get(key, default)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _require_project(self) -> None:
        """Raise RuntimeError if no pow.toml was found during initialization."""
        if self._project_root is None:
            raise RuntimeError("Project not initialized: pow.toml not found")
