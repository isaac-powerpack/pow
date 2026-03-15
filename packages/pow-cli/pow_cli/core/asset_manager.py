"""AssetManager — manages local asset path setup for pow."""

from __future__ import annotations

import os
import importlib.resources
import tomlkit
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from .models.pow_config import PowConfig
from .models.system_config import SystemConfig
from .models.asset_profile import AssetProfile


# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class AssetListEntry:
    """A single registry asset enriched with live profile data (if available)."""

    group_name: str
    title: str
    name: str
    size: str             # human-readable e.g. '2.62 GB'
    status: str = "pending"
    completion_pct: float = 0.0


@dataclass
class AssetListData:
    """Result of get_asset_list_data(), consumed by the CLI."""

    local_path: str                              # empty = not configured
    symlink_ok: bool                             # symlink exists → real dir
    entries: List[AssetListEntry] = field(default_factory=list)


class AssetError(Exception):
    """Raised when an asset operation fails with a user-facing message."""


# ── Registry configuration ───────────────────────────────────────────────────

REGISTRIES = [
    {
        "file": "isaacsim_assets_5_1_0.toml",
        "root_key": "isaacsim_assets",
        "group_keys": ["isaacsim_5_1_0"],
    },
    {
        "file": "omniverse_assets.toml",
        "root_key": "omniverse",
        "group_keys": [
            "omni_3d_assets",
            "omni_sim_ready",
            "omni_materials",
            "omni_environments",
            "omni_workflows",
        ],
    },
]


class AssetManager:
    """Handles local asset path configuration, alias registration, and kit patching."""

    POW_ASSETS_ALIAS = "pow-assets"
    OMNIVERSE_TOML_PATH = Path.home() / ".nvidia-omniverse" / "config" / "omniverse.toml"

    # Sentinel comments used to detect an existing patch block in .kit files
    _KIT_PATCH_START = "# Local asset settings (added by pow cli)"
    _KIT_PATCH_END   = "# End: Local asset settings (added by pow cli)"

    # S3 URL keys for alias-support flags
    _ISAACSIM_S3_ALIAS_KEYS = (
        "http://omniverse-content-production.s3.us-west-2.amazonaws.com",
        "https://omniverse-content-production.s3.us-west-2.amazonaws.com",
        "http://omniverse-content-production.s3-us-west-2.amazonaws.com",
        "https://omniverse-content-production.s3-us-west-2.amazonaws.com",
    )
    _SIM_READY_S3_ALIAS_KEYS = (
        "http://omniverse-content-staging.s3.us-west-2.amazonaws.com",
        "https://omniverse-content-staging.s3.us-west-2.amazonaws.com",
    )

    def __init__(self):
        self._config = PowConfig()

    # ── Path accessors ────────────────────────────────────────────────────────

    @property
    def global_dir(self) -> Path:
        """The global pow directory (e.g. ~/.pow)."""
        return self._config.global_path

    def get_system_toml_path(self) -> Path:
        return self.global_dir / "system.toml"

    def get_assets_symlink_path(self) -> Path:
        return self.global_dir / "assets"

    def get_kit_path(self) -> Path:
        return (
            self.global_dir / "isaacsim" / "5.1.0" / "apps" / "isaacsim.exp.base.kit"
        )

    # ── Configuration queries ─────────────────────────────────────────────────

    def get_local_asset_path(self) -> str:
        """Get the currently configured local asset path from system.toml."""
        path = self.get_system_toml_path()
        if not path.exists():
            return ""
        return SystemConfig.from_file(path).asset.local_asset_path

    def is_asset_configured(self) -> bool:
        """Return True if [asset] is already set in system.toml."""
        return bool(self.get_local_asset_path())

    # ── Asset list data ───────────────────────────────────────────────────────

    def get_asset_list_data(self) -> AssetListData:
        """Return registry entries enriched with live profile data from all registries."""
        local_path = self.get_local_asset_path()
        symlink = self.get_assets_symlink_path()
        symlink_ok = symlink.is_symlink() and symlink.resolve().is_dir()

        profile = self._load_profile(symlink) if (local_path and symlink_ok) else None
        entries = self._load_registry_entries(profile)

        return AssetListData(
            local_path=local_path,
            symlink_ok=symlink_ok,
            entries=entries,
        )

    # ── set / unset ───────────────────────────────────────────────────────────

    def set_local_asset_path(self, asset_path: str) -> str:
        """Configure the local asset path.

        Steps:
        1. Reject if asset config in system.toml is already set.
        2. Reject if .pow/assets already exists and is a symlink.
        3. Validate the given path exists and is a directory.
        4. Resolve to an absolute path.
        5. Create the .pow/assets symlink.
        6. Write [asset] config in system.toml.
        7. Register pow-assets alias in omniverse.toml.

        Returns:
            The resolved absolute path that was set.

        Raises:
            AssetError: If any validation or operation step fails.
        """
        self._reject_if_already_configured()
        self._reject_if_symlink_exists()
        abs_path = self._validate_and_resolve(asset_path)

        self.global_dir.mkdir(parents=True, exist_ok=True)
        os.symlink(abs_path, self.get_assets_symlink_path())
        self._write_system_toml(abs_path)
        self._register_omniverse_alias(abs_path)

        return str(abs_path)

    def unset_local_asset_path(self) -> dict[str, str]:
        """Remove all asset configuration set by set_local_asset_path.

        Each step is performed independently; failures are collected and reported
        without aborting the remaining steps.

        Returns:
            A dict mapping step label → outcome message (for CLI feedback).

        Raises:
            AssetError: If none of the expected state was found (nothing to unset).
        """
        results: dict[str, str] = {}
        any_action = False

        steps = [
            ("Symlink",                    self._unset_symlink),
            ("system.toml [asset]",        self._unset_system_toml),
            ("omniverse.toml [alias]",     self._unset_omniverse_aliases),
            ("isaacsim.exp.base.kit patch", self._unset_kit_patch),
        ]

        for label, step_fn in steps:
            try:
                outcome = step_fn()
                results[label] = outcome
                if "skipped" not in outcome.lower():
                    any_action = True
            except Exception as exc:
                results[label] = f"Failed: {exc}"

        if not any_action:
            raise AssetError(
                "No asset configuration was found. Nothing to unset.\n"
                "Run 'pow asset set <path>' to configure an asset path first."
            )

        return results

    # ── Kit patching ──────────────────────────────────────────────────────────

    def patch_isaacsim_kit(self, use_local_path: str) -> bool:
        """Append local asset settings block to isaacsim.exp.base.kit.

        Returns:
            True if the file was patched, False if it was already patched.

        Raises:
            AssetError: If the .kit file does not exist.
        """
        kit_path = self.get_kit_path()
        if not kit_path.exists():
            raise AssetError(
                f"Kit file not found: '{kit_path}'\n"
                "Make sure Isaac Sim is installed under the pow global directory."
            )

        existing = kit_path.read_text(encoding="utf-8")
        if self._KIT_PATCH_START in existing:
            return False

        patch_block = self._build_kit_patch_block()
        with kit_path.open("a", encoding="utf-8") as fh:
            fh.write(patch_block)

        return True

    def unpatch_isaacsim_kit(self) -> bool:
        """Remove the pow-added settings block from isaacsim.exp.base.kit.

        Returns:
            True if the block was found and removed, False if it was not present.
        """
        kit_path = self.get_kit_path()
        if not kit_path.exists():
            return False

        text = kit_path.read_text(encoding="utf-8")
        if self._KIT_PATCH_START not in text:
            return False

        start_idx = text.find(self._KIT_PATCH_START)
        end_idx = text.find(self._KIT_PATCH_END, start_idx)
        if end_idx == -1:
            return False  # Malformed patch — leave the file untouched

        end_idx += len(self._KIT_PATCH_END)

        # Consume any trailing newline after the end sentinel
        if end_idx < len(text) and text[end_idx] == "\n":
            end_idx += 1

        # Strip any extra blank lines immediately before the patch block
        pre = text[:start_idx]
        if pre.endswith("\n"):
            pre = pre.rstrip("\n") + "\n"

        kit_path.write_text(pre + text[end_idx:], encoding="utf-8")
        return True

    # ── S3 alias registration ─────────────────────────────────────────────────

    def register_isaacsim_s3_aliases(self) -> None:
        """Add Isaac Sim production S3 URL → assets symlink mappings to omniverse.toml."""
        self._write_s3_aliases(self._ISAACSIM_S3_ALIAS_KEYS)

    def register_sim_ready_s3_aliases(self) -> None:
        """Add Omniverse staging S3 URL → assets symlink mappings to omniverse.toml."""
        self._write_s3_aliases(self._SIM_READY_S3_ALIAS_KEYS)

    # ── Private: validation helpers ───────────────────────────────────────────

    def _reject_if_already_configured(self) -> None:
        if self.is_asset_configured():
            existing = self.get_local_asset_path()
            raise AssetError(
                f"Asset path is already configured: '{existing}'\n"
                "Run 'pow asset unset' to remove the current configuration first."
            )

    def _reject_if_symlink_exists(self) -> None:
        assets_symlink = self.get_assets_symlink_path()
        if assets_symlink.is_symlink():
            raise AssetError(
                f"'{assets_symlink}' is already a symlink.\n"
                "Remove it manually before running this command."
            )

    @staticmethod
    def _validate_and_resolve(asset_path: str) -> Path:
        given = Path(asset_path)
        if not given.exists():
            raise AssetError(f"Path does not exist: '{asset_path}'")
        if not given.is_dir():
            raise AssetError(f"Path is not a directory: '{asset_path}'")
        return given.resolve()

    # ── Private: system.toml I/O ──────────────────────────────────────────────

    def _write_system_toml(self, abs_path: Path) -> None:
        toml_path = self.get_system_toml_path()
        toml_path.parent.mkdir(parents=True, exist_ok=True)

        system_config = (
            SystemConfig.from_file(toml_path)
            if toml_path.exists()
            else SystemConfig.default()
        )

        system_config.asset.local_asset_path = str(abs_path)
        system_config.asset.use_local_asset = True

        self._save_system_config(toml_path, system_config)

    def _clear_system_toml_asset(self) -> bool:
        """Reset [asset] in system.toml to defaults. Returns True if it was set."""
        toml_path = self.get_system_toml_path()
        if not toml_path.exists():
            return False

        system_config = SystemConfig.from_file(toml_path)
        was_set = bool(system_config.asset.local_asset_path)

        system_config.asset.local_asset_path = ""
        system_config.asset.use_local_asset = False

        self._save_system_config(toml_path, system_config)
        return was_set

    @staticmethod
    def _save_system_config(toml_path: Path, system_config: SystemConfig) -> None:
        doc = tomlkit.document()
        for section, values in system_config.to_dict().items():
            table = tomlkit.table()
            for k, v in values.items():
                table.add(k, v)
            doc.add(section, table)
        toml_path.write_text(tomlkit.dumps(doc))

    # ── Private: omniverse.toml I/O ───────────────────────────────────────────

    def _read_omniverse_doc(self) -> tomlkit.TOMLDocument:
        """Load or create the omniverse.toml document."""
        if self.OMNIVERSE_TOML_PATH.exists():
            return tomlkit.parse(self.OMNIVERSE_TOML_PATH.read_text())
        return tomlkit.document()

    def _save_omniverse_doc(self, doc: tomlkit.TOMLDocument) -> None:
        self.OMNIVERSE_TOML_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.OMNIVERSE_TOML_PATH.write_text(tomlkit.dumps(doc))

    def _register_omniverse_alias(self, abs_path: Path) -> None:
        """Add or update 'pow-assets' entry in [alias] of omniverse.toml."""
        doc = self._read_omniverse_doc()
        if "alias" not in doc:
            doc.add("alias", tomlkit.table())
        doc["alias"][self.POW_ASSETS_ALIAS] = str(self.get_assets_symlink_path())
        self._save_omniverse_doc(doc)

    def _clear_omniverse_aliases(self) -> bool:
        """Remove entire [alias] section from omniverse.toml. Returns True if removed."""
        if not self.OMNIVERSE_TOML_PATH.exists():
            return False
        doc = self._read_omniverse_doc()
        if "alias" not in doc:
            return False
        del doc["alias"]
        self._save_omniverse_doc(doc)
        return True

    def _write_s3_aliases(self, keys: tuple[str, ...]) -> None:
        """Write the given S3 URL keys → assets symlink into omniverse.toml [alias]."""
        doc = self._read_omniverse_doc()
        if "alias" not in doc:
            doc.add("alias", tomlkit.table())
        symlink_path = str(self.get_assets_symlink_path())
        for url in keys:
            doc["alias"][url] = symlink_path
        self._save_omniverse_doc(doc)

    # ── Private: unset step functions ─────────────────────────────────────────

    def _unset_symlink(self) -> str:
        symlink = self.get_assets_symlink_path()
        if symlink.is_symlink():
            symlink.unlink()
            return f"Removed {symlink}"
        return "Not found — skipped"

    def _unset_system_toml(self) -> str:
        return "Cleared" if self._clear_system_toml_asset() else "Not configured — skipped"

    def _unset_omniverse_aliases(self) -> str:
        return "Removed" if self._clear_omniverse_aliases() else "Not found — skipped"

    def _unset_kit_patch(self) -> str:
        return "Removed" if self.unpatch_isaacsim_kit() else "Patch block not found — skipped"

    # ── Private: asset data loading ───────────────────────────────────────────

    @staticmethod
    def _load_profile(symlink: Path) -> AssetProfile | None:
        """Load asset-profile.toml from the symlink target, if it exists."""
        profile_path = symlink.resolve() / "asset-profile.toml"
        if not profile_path.exists():
            return None
        try:
            return AssetProfile.from_file(profile_path)
        except Exception:
            return None

    @staticmethod
    def _load_registry_entries(profile: AssetProfile | None) -> list[AssetListEntry]:
        """Parse all configured registry files and merge with profile data."""
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]

        entries: list[AssetListEntry] = []

        for reg_config in REGISTRIES:
            try:
                registry_bytes = (
                    importlib.resources.files("pow_cli")
                    .joinpath("data")
                    .joinpath("asset-registry")
                    .joinpath(reg_config["file"])
                    .read_bytes()
                )
                registry = tomllib.loads(registry_bytes.decode())
                root = registry.get(reg_config["root_key"], {})

                for group_key in reg_config["group_keys"]:
                    for raw in root.get(group_key, []):
                        name = raw.get("name", "")
                        status = "not-downloaded"
                        completion_pct = 0.0

                        if profile:
                            asset_entry = profile.get_asset(group_key, name)
                            if asset_entry:
                                status = asset_entry.status
                                completion_pct = asset_entry.completion_pct

                        entries.append(
                            AssetListEntry(
                                group_name=group_key,
                                title=raw.get("title", name),
                                name=name,
                                size=raw.get("size", "—"),
                                status=status,
                                completion_pct=completion_pct,
                            )
                        )
            except Exception:
                continue

        return entries

    # ── Private: kit patch block builder ──────────────────────────────────────

    def _build_kit_patch_block(self) -> str:
        """Build the full kit patch text block."""
        assets_root = str(self.get_assets_symlink_path())
        isaac_root = f"{assets_root}/Assets/Isaac/{PowConfig.ISAACSIM_VERSION}/Isaac"

        folders = [
            f"{isaac_root}/{sub}"
            for sub in (
                "Robots", "People", "IsaacLab", "Props",
                "Environments", "Materials", "Samples", "Sensors",
            )
        ]

        folder_block = self._fmt_kit_folder_list(folders)

        return (
            "\n"
            f"{self._KIT_PATCH_START}\n"
            "[settings]\n"
            f'exts."isaacsim.asset.browser".visible_after_startup = true\n'
            f'persistent.isaac.asset_root.default = "{assets_root}/Assets/Isaac/{PowConfig.ISAACSIM_VERSION}"\n'
            f'exts."isaacsim.gui.content_browser".folders =\n'
            f"{folder_block}\n"
            "\n"
            f'exts."isaacsim.asset.browser".folders =\n'
            f"{folder_block}\n"
            f"{self._KIT_PATCH_END}\n"
        )

    @staticmethod
    def _fmt_kit_folder_list(items: list[str]) -> str:
        lines = ["    ["]
        for item in items:
            lines.append(f'        "{item}",')
        lines.append("    ]")
        return "\n".join(lines)