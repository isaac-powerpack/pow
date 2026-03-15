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



    # Sentinel comment used to detect an existing patch block
    _KIT_PATCH_START = "# Local asset settings (added by pow cli)"
    _KIT_PATCH_END   = "# End: Local asset settings (added by pow cli)"

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
        4. Remove the pow patch block from isaacsim.exp.base.kit (if present).

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

        # Step 4 — Remove pow patch block from isaacsim.exp.base.kit (silently skipped if absent)
        try:
            removed = self.unpatch_isaacsim_kit()
            if removed:
                results["isaacsim.exp.base.kit patch"] = "Removed"
                any_action = True
            else:
                results["isaacsim.exp.base.kit patch"] = "Patch block not found — skipped"
        except Exception as exc:
            results["isaacsim.exp.base.kit patch"] = f"Failed: {exc}"

        if not any_action:
            raise AssetError(
                "No asset configuration was found. Nothing to unset.\n"
                "Run 'pow asset set <path>' to configure an asset path first."
            )

        return results

    # ── Private helpers ───────────────────────────────────────────────────────

    def patch_isaacsim_kit(self, use_local_path: str) -> bool:
        """Append local asset settings block to isaacsim.exp.base.kit.

        Uses plain string manipulation — no tomlkit / tomllib involved.

        Args:
            use_local_path: Absolute path to the local assets root directory (unused
                for path values — the symlink is always used so the kit config stays
                portable across path changes).

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
            return False  # Already patched — skip

        # Always use the symlink so the kit config doesn't embed the raw source path
        assets_root = str(self.get_assets_symlink_path())
        isaac_root = f"{assets_root}/Assets/Isaac/{PowConfig.ISAACSIM_VERSION}/Isaac"

        folders = [
            f"{isaac_root}/Robots",
            f"{isaac_root}/People",
            f"{isaac_root}/IsaacLab",
            f"{isaac_root}/Props",
            f"{isaac_root}/Environments",
            f"{isaac_root}/Materials",
            f"{isaac_root}/Samples",
            f"{isaac_root}/Sensors",
        ]

        def _fmt_folder_list(items: list[str]) -> str:
            lines = ["    ["]
            for item in items:
                lines.append(f'        "{item}",')
            lines.append("    ]")
            return "\n".join(lines)

        folder_block = _fmt_folder_list(folders)

        patch_block = (
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

        with kit_path.open("a", encoding="utf-8") as fh:
            fh.write(patch_block)

        return True

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

        doc["alias"][self.POW_ASSETS_ALIAS] = str(self.get_assets_symlink_path())
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

    # S3 URL keys added by the isaacsim alias-support flag
    _ISAACSIM_S3_ALIAS_KEYS = (
        "http://omniverse-content-production.s3.us-west-2.amazonaws.com",
        "https://omniverse-content-production.s3.us-west-2.amazonaws.com",
        "http://omniverse-content-production.s3-us-west-2.amazonaws.com",
        "https://omniverse-content-production.s3-us-west-2.amazonaws.com",
    )

    # S3 URL keys added by the sim-ready alias-support flag
    _SIM_READY_S3_ALIAS_KEYS = (
        "http://omniverse-content-staging.s3.us-west-2.amazonaws.com",
        "https://omniverse-content-staging.s3.us-west-2.amazonaws.com",
    )

    def _write_s3_aliases(self, keys: tuple[str, ...]) -> None:
        """Write the given S3 URL keys → assets symlink into omniverse.toml [alias]."""
        toml_path = self.OMNIVERSE_TOML_PATH
        toml_path.parent.mkdir(parents=True, exist_ok=True)

        if toml_path.exists():
            doc = tomlkit.parse(toml_path.read_text())
        else:
            doc = tomlkit.document()

        if "alias" not in doc:
            doc.add("alias", tomlkit.table())

        symlink_path = str(self.get_assets_symlink_path())
        for url in keys:
            doc["alias"][url] = symlink_path

        toml_path.write_text(tomlkit.dumps(doc))

    def register_isaacsim_s3_aliases(self) -> None:
        """Add Isaac Sim production S3 URL → assets symlink mappings to omniverse.toml."""
        self._write_s3_aliases(self._ISAACSIM_S3_ALIAS_KEYS)

    def register_sim_ready_s3_aliases(self) -> None:
        """Add Omniverse staging S3 URL → assets symlink mappings to omniverse.toml."""
        self._write_s3_aliases(self._SIM_READY_S3_ALIAS_KEYS)

    def unpatch_isaacsim_kit(self) -> bool:
        """Remove the pow-added settings block from isaacsim.exp.base.kit.

        Uses plain string manipulation — no tomlkit / tomllib involved.
        Strips from the _KIT_PATCH_START sentinel line through the _KIT_PATCH_END
        sentinel line (inclusive), including any leading blank line before the block.

        Returns:
            True if the block was found and removed, False if it was not present.
        """
        kit_path = self.get_kit_path()
        if not kit_path.exists():
            return False

        text = kit_path.read_text(encoding="utf-8")
        if self._KIT_PATCH_START not in text:
            return False  # Nothing to remove

        start_idx = text.find(self._KIT_PATCH_START)
        end_idx   = text.find(self._KIT_PATCH_END, start_idx)
        if end_idx == -1:
            return False  # Malformed patch — leave the file untouched

        end_idx += len(self._KIT_PATCH_END)

        # Consume any trailing newline after the end sentinel
        if end_idx < len(text) and text[end_idx] == "\n":
            end_idx += 1

        # Also strip any blank line immediately before the patch block
        pre = text[:start_idx]
        if pre.endswith("\n"):
            pre = pre.rstrip("\n") + "\n"

        new_text = pre + text[end_idx:]
        kit_path.write_text(new_text, encoding="utf-8")
        return True


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