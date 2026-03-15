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


# ── Asset list data structures ────────────────────────────────────────────────


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


class AssetManager:
    """Handles the management of assets, including configuration of local asset paths."""

    OMNIVERSE_TOML_PATH = Path.home() / ".nvidia-omniverse" / "config" / "omniverse.toml"
    
    # Registry configurations
    REGISTRIES = [
        {
            "file": "isaacsim_assets_5_1_0.toml",
            "root_key": "isaacsim_assets",
            "group_keys": ["isaacsim_5_1_0"]
        },
        {
            "file": "omniverse_assets.toml",
            "root_key": "omniverse",
            "group_keys": [
                "omni_3d_assets", 
                "omni_sim_ready", 
                "omni_materials", 
                "omni_environments", 
                "omni_workflows"
            ]
        }
    ]
    
    POW_ASSETS_ALIAS = "pow-assets"

    # Keys to remove from [settings] in isaacsim.exp.base.kit on unset.
    # Dotted keys that contain special chars must be quoted per TOML spec.
    _KIT_SETTINGS_KEYS_TO_UNSET = (
        'exts."isaacsim.asset.browser".visible_after_startup',
        "persistent.isaac.asset_root.default",
        'exts."isaacsim.gui.content_browser".folders',
        'exts."isaacsim.asset.browser".folders',
    )

    def __init__(self):
        self._config = PowConfig()

    # ── Paths ────────────────────────────────────────────────────────────────

    @property
    def global_dir(self) -> Path:
        """The global pow directory (e.g. ~/.pow)."""
        return self._config.global_path

    def get_system_toml_path(self) -> Path:
        """Get the path to the system.toml file."""
        return self.global_dir / "system.toml"

    def get_assets_symlink_path(self) -> Path:
        """Path to the .pow/assets symlink."""
        return self.global_dir / "assets"

    def get_kit_path(self) -> Path:
        """Path to the isaacsim.exp.base.kit file inside the global pow directory."""
        return self.global_dir / "isaacsim" / "5.1.0" / "apps" / "isaacsim.exp.base.kit"

    # ── Readers ──────────────────────────────────────────────────────────────

    def get_local_asset_path(self) -> str:
        """Get the currently configured local asset path from system.toml."""
        path = self.get_system_toml_path()
        if not path.exists():
            return ""
        system_config = SystemConfig.from_file(path)
        return system_config.asset.local_asset_path

    def is_asset_configured(self) -> bool:
        """Return True if [asset] is already set in system.toml."""
        return bool(self.get_local_asset_path())

    # ── get_asset_list_data ──────────────────────────────────────────────────

    def get_asset_list_data(self) -> AssetListData:
        """Return registry entries enriched with live profile data from all registries."""
        local_path = self.get_local_asset_path()
        symlink = self.get_assets_symlink_path()
        symlink_ok = symlink.is_symlink() and symlink.resolve().is_dir()

        # Load registries
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]

        entries: list[AssetListEntry] = []
        
        # Load profile once
        profile: AssetProfile | None = None
        if local_path and symlink_ok:
            profile_path = symlink.resolve() / "asset-profile.toml"
            if profile_path.exists():
                try:
                    profile = AssetProfile.from_file(profile_path)
                except Exception:
                    profile = None

        for reg_config in self.REGISTRIES:
            try:
                registry_ref = (
                    importlib.resources.files("pow_cli")
                    .joinpath("data")
                    .joinpath("asset-registry")
                    .joinpath(reg_config["file"])
                )
                registry_bytes = registry_ref.read_bytes()
                registry = tomllib.loads(registry_bytes.decode())
                
                root = registry.get(reg_config["root_key"], {})
                
                for group_key in reg_config["group_keys"]:
                    raw_assets = root.get(group_key, [])
                    
                    for raw in raw_assets:
                        name = raw.get("name", "")
                        status = "not-downloaded"
                        completion_pct = 0.0

                        if profile:
                            # Try to find in profile
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
                # Skip registries that fail to load
                continue

        return AssetListData(
            local_path=local_path,
            symlink_ok=symlink_ok,
            entries=entries,
        )

    # ── set_local_asset_path ─────────────────────────────────────────────────

    def set_local_asset_path(self, asset_path: str) -> str:
        """Configure the local asset path.

        Performs the following steps:
        1. Reject if asset config in system.toml is already set.
        2. Reject if .pow/assets already exists and is a symlink.
        3. Reject if <assets-path> is invalid or does not exist.
        4. Resolve <assets-path> to an absolute path.
        5. Create the .pow/assets symlink pointing to <assets-path>.
        6. Write [asset] config in system.toml.
        7. Register pow-assets alias in omniverse.toml.

        Args:
            asset_path: Path to the local asset directory (relative or absolute).

        Returns:
            The resolved absolute path that was set.

        Raises:
            AssetError: If any validation or operation step fails.
        """
        # Step 1 — Reject if asset config is already set
        if self.is_asset_configured():
            existing = self.get_local_asset_path()
            raise AssetError(
                f"Asset path is already configured: '{existing}'\n"
                "Run 'pow asset unset' to remove the current configuration first."
            )

        # Step 2 — Reject if .pow/assets already exists as a symlink
        assets_symlink = self.get_assets_symlink_path()
        if assets_symlink.is_symlink():
            raise AssetError(
                f"'{assets_symlink}' is already a symlink.\n"
                "Remove it manually before running this command."
            )

        # Step 3 — Validate the given path
        given = Path(asset_path)
        if not given.exists():
            raise AssetError(f"Path does not exist: '{asset_path}'")
        if not given.is_dir():
            raise AssetError(f"Path is not a directory: '{asset_path}'")

        # Step 4 — Resolve to absolute path
        abs_path = given.resolve()

        # Step 5 — Create .pow/assets symlink
        self.global_dir.mkdir(parents=True, exist_ok=True)
        os.symlink(abs_path, assets_symlink)

        # Step 6 — Write [asset] config in system.toml
        self._write_system_toml(abs_path)

        # Step 7 — Register pow-assets alias in omniverse.toml
        self._register_omniverse_alias(abs_path)

        return str(abs_path)

    # ── unset_local_asset_path ───────────────────────────────────────────────

    def unset_local_asset_path(self) -> dict[str, str]:
        """Remove all asset configuration set by set_local_asset_path.

        Each step is performed independently; failures are collected and reported
        without aborting the remaining steps.

        Steps:
        1. Remove the .pow/assets symlink (if it exists).
        2. Clear [asset] config in system.toml (reset to defaults).
        3. Remove all entries under [alias] in omniverse.toml.
        4. Remove specific keys from [settings] in isaacsim.exp.base.kit.

        Returns:
            A dict mapping step label → outcome message (for CLI feedback).

        Raises:
            AssetError: If none of the expected state was found (nothing to unset).
        """
        results: dict[str, str] = {}
        any_action = False

        # Step 1 — Remove .pow/assets symlink
        symlink = self.get_assets_symlink_path()
        try:
            if symlink.is_symlink():
                symlink.unlink()
                results["Symlink"] = f"Removed {symlink}"
                any_action = True
            else:
                results["Symlink"] = "Not found — skipped"
        except OSError as exc:
            results["Symlink"] = f"Failed to remove: {exc}"

        # Step 2 — Clear [asset] in system.toml
        try:
            removed = self._clear_system_toml_asset()
            if removed:
                results["system.toml [asset]"] = "Cleared"
                any_action = True
            else:
                results["system.toml [asset]"] = "Not configured — skipped"
        except Exception as exc:
            results["system.toml [asset]"] = f"Failed: {exc}"

        # Step 3 — Remove [alias] section from omniverse.toml
        try:
            removed = self._clear_omniverse_aliases()
            if removed:
                results["omniverse.toml [alias]"] = "Removed"
                any_action = True
            else:
                results["omniverse.toml [alias]"] = "Not found — skipped"
        except Exception as exc:
            results["omniverse.toml [alias]"] = f"Failed: {exc}"

        # Step 4 — Remove specific keys from isaacsim.exp.base.kit [settings]
        try:
            removed_keys = self._unset_kit_settings()
            if removed_keys:
                results["isaacsim.exp.base.kit [settings]"] = (
                    f"Removed {len(removed_keys)} key(s): {', '.join(removed_keys)}"
                )
                any_action = True
            else:
                results["isaacsim.exp.base.kit [settings]"] = "No matching keys — skipped"
        except Exception as exc:
            results["isaacsim.exp.base.kit [settings]"] = f"Failed: {exc}"

        if not any_action:
            raise AssetError(
                "No asset configuration was found. Nothing to unset.\n"
                "Run 'pow asset set <path>' to configure an asset path first."
            )

        return results

    # ── Private helpers ───────────────────────────────────────────────────────

    def _write_system_toml(self, abs_path: Path) -> None:
        """Write or update [asset] section in system.toml."""
        toml_path = self.get_system_toml_path()
        toml_path.parent.mkdir(parents=True, exist_ok=True)

        if toml_path.exists():
            system_config = SystemConfig.from_file(toml_path)
        else:
            system_config = SystemConfig.default()

        system_config.asset.local_asset_path = str(abs_path)
        system_config.asset.use_local_asset = True

        doc = tomlkit.document()
        for section, values in system_config.to_dict().items():
            table = tomlkit.table()
            for k, v in values.items():
                table.add(k, v)
            doc.add(section, table)

        toml_path.write_text(tomlkit.dumps(doc))

    def _clear_system_toml_asset(self) -> bool:
        """Reset [asset] in system.toml to defaults. Returns True if it was set."""
        toml_path = self.get_system_toml_path()
        if not toml_path.exists():
            return False

        system_config = SystemConfig.from_file(toml_path)
        was_set = bool(system_config.asset.local_asset_path)

        system_config.asset.local_asset_path = ""
        system_config.asset.use_local_asset = False

        doc = tomlkit.document()
        for section, values in system_config.to_dict().items():
            table = tomlkit.table()
            for k, v in values.items():
                table.add(k, v)
            doc.add(section, table)

        toml_path.write_text(tomlkit.dumps(doc))
        return was_set

    def _register_omniverse_alias(self, abs_path: Path) -> None:
        """Add or update 'pow-assets' entry in [alias] of omniverse.toml."""
        toml_path = self.OMNIVERSE_TOML_PATH
        toml_path.parent.mkdir(parents=True, exist_ok=True)

        if toml_path.exists():
            doc = tomlkit.parse(toml_path.read_text())
        else:
            doc = tomlkit.document()

        if "alias" not in doc:
            doc.add("alias", tomlkit.table())

        doc["alias"][self.POW_ASSETS_ALIAS] = str(abs_path)
        toml_path.write_text(tomlkit.dumps(doc))

    def _clear_omniverse_aliases(self) -> bool:
        """Remove entire [alias] section from omniverse.toml. Returns True if removed."""
        toml_path = self.OMNIVERSE_TOML_PATH
        if not toml_path.exists():
            return False

        doc = tomlkit.parse(toml_path.read_text())
        if "alias" not in doc:
            return False

        del doc["alias"]
        toml_path.write_text(tomlkit.dumps(doc))
        return True

    def _unset_kit_settings(self) -> list[str]:
        """Remove specific keys from [settings] in isaacsim.exp.base.kit.

        Uses tomlkit to parse and edit the file in-place.
        Returns a list of keys that were actually removed.
        """
        kit_path = self.get_kit_path()
        if not kit_path.exists():
            return []

        doc = tomlkit.parse(kit_path.read_text())

        settings = doc.get("settings")
        if settings is None:
            return []

        removed: list[str] = []

        for dotted_key in self._KIT_SETTINGS_KEYS_TO_UNSET:
            # Walk the nested tomlkit structure using the dotted key segments.
            # Keys like exts."isaacsim.asset.browser".visible_after_startup
            # need careful splitting that respects quoted segments.
            segments = _split_dotted_key(dotted_key)
            _delete_nested(settings, segments, removed, dotted_key)

        kit_path.write_text(tomlkit.dumps(doc))
        return removed


# ── Module-level helpers ──────────────────────────────────────────────────────


def _split_dotted_key(key: str) -> list[str]:
    """Split a TOML dotted key respecting quoted segments.

    e.g. 'exts."isaacsim.asset.browser".visible_after_startup'
         → ['exts', 'isaacsim.asset.browser', 'visible_after_startup']
    """
    segments: list[str] = []
    current = ""
    in_quotes = False

    for ch in key:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == "." and not in_quotes:
            if current:
                segments.append(current)
            current = ""
        else:
            current += ch

    if current:
        segments.append(current)

    return segments


def _delete_nested(
    table: object,
    segments: list[str],
    removed: list[str],
    original_key: str,
) -> None:
    """Recursively walk *table* following *segments* and delete the leaf key.

    Appends *original_key* to *removed* if the deletion succeeded.
    Silently skips if any intermediate segment is missing.
    """
    if not segments:
        return

    head, *tail = segments

    try:
        node = table[head]  # type: ignore[index]
    except (KeyError, TypeError):
        return  # key or path not present — nothing to do

    if not tail:
        # Leaf — delete it
        try:
            del table[head]  # type: ignore[attr-defined]
            removed.append(original_key)
        except (KeyError, TypeError):
            pass
    else:
        _delete_nested(node, tail, removed, original_key)