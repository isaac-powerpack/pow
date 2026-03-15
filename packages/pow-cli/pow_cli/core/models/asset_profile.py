"""AssetProfile model — represents the data in an asset-profile.toml file."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


# ── AssetEntry ────────────────────────────────────────────────────────────────


@dataclass
class AssetEntry:
    """A single downloadable asset pack within a group.

    Fields
    ------
    name             : Unique identifier within the group.
    status           : Lifecycle state — one of:
                       "not-downloaded" | "in-progress" | "downloaded" | "error"
    total_bytes      : Expected total size once complete (0 = unknown).
    downloaded_bytes : Bytes received so far.
    aria2_gid        : Active aria2 download GID; empty when not downloading.
    archive_files    : Ordered list of archive file paths relative to the
                       asset root (reassemble multi-part zips in list order).
    extract_info_file: Filename (relative to artifacts_dir) listing extracted
                       paths produced by unpacking this asset.
    """

    name: str
    status: str
    total_bytes: int
    downloaded_bytes: int
    archive_files: List[str]
    extract_info_file: str
    aria2_gid: str = ""

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict) -> AssetEntry:
        return cls(
            name=data["name"],
            status=data.get("status", "not-downloaded"),
            total_bytes=data.get("total_bytes", 0),
            downloaded_bytes=data.get("downloaded_bytes", 0),
            archive_files=data.get("archive_files", []),
            extract_info_file=data.get("extract_info_file", ""),
            aria2_gid=data.get("aria2_gid", ""),
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "status": self.status,
            "total_bytes": self.total_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "archive_files": self.archive_files,
            "extract_info_file": self.extract_info_file,
        }
        if self.aria2_gid:
            d["aria2_gid"] = self.aria2_gid
        return d

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def is_complete(self) -> bool:
        """True when all bytes have been downloaded."""
        return self.total_bytes > 0 and self.downloaded_bytes >= self.total_bytes

    @property
    def completion_pct(self) -> float:
        """Download progress as a percentage (0–100)."""
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, self.downloaded_bytes / self.total_bytes * 100)


# ── AssetGroup ────────────────────────────────────────────────────────────────


@dataclass
class AssetGroup:
    """A named collection of asset packs that share a common theme or release.

    Maps to ``[[group]]`` sections in the TOML file.
    """

    name: str
    assets: List[AssetEntry] = field(default_factory=list)

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict) -> AssetGroup:
        assets = [AssetEntry.from_dict(a) for a in data.get("asset", [])]
        return cls(name=data["name"], assets=assets)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "asset": [a.to_dict() for a in self.assets],
        }


# ── ProfileMeta ───────────────────────────────────────────────────────────────


@dataclass
class ProfileMeta:
    """Metadata stored under ``[profile]`` in asset-profile.toml.

    Fields
    ------
    schema_version : Semver string used for migration compatibility checks.
    created_at     : UTC timestamp of initial file creation.
    updated_at     : UTC timestamp of the last write.
    artifacts_dir  : Base directory for all ``extract_info_file`` paths.
                     Relative to the asset root directory.
    """

    schema_version: str
    artifacts_dir: str = ".asset-artifacts"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict) -> ProfileMeta:
        return cls(
            schema_version=data.get("schema_version", "0.0.0"),
            artifacts_dir=data.get("artifacts_dir", ".asset-artifacts"),
            created_at=data.get("created_at", datetime.now(timezone.utc)),
            updated_at=data.get("updated_at", datetime.now(timezone.utc)),
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "schema_version": self.schema_version,
            "artifacts_dir": self.artifacts_dir,
        }


# ── AssetProfile ──────────────────────────────────────────────────────────────


@dataclass
class AssetProfile:
    """In-memory representation of an asset-profile.toml file.

    TOML structure
    --------------
    [profile]
      created_at, updated_at, schema_version, artifacts_dir

    [[group]]
      name = "..."
      [[group.asset]]
        name, status, total_bytes, downloaded_bytes,
        aria2_gid (optional), archive_files, extract_info_file
    """

    meta: ProfileMeta
    groups: List[AssetGroup] = field(default_factory=list)

    # ── Constructors ─────────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict) -> AssetProfile:
        meta = ProfileMeta.from_dict(data.get("profile", {}))
        groups = [AssetGroup.from_dict(g) for g in data.get("group", [])]
        return cls(meta=meta, groups=groups)

    @classmethod
    def from_file(cls, path: Path) -> AssetProfile:
        """Load an AssetProfile from an existing asset-profile.toml file."""
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]

        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_dict(data)

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "profile": self.meta.to_dict(),
            "group": [g.to_dict() for g in self.groups],
        }

    # ── Lookup helpers ───────────────────────────────────────────────────────

    def get_group(self, name: str) -> Optional[AssetGroup]:
        """Return the group with the given name, or None."""
        return next((g for g in self.groups if g.name == name), None)

    def get_asset(self, group_name: str, asset_name: str) -> Optional[AssetEntry]:
        """Return a specific asset entry, or None if not found."""
        group = self.get_group(group_name)
        if group is None:
            return None
        return next((a for a in group.assets if a.name == asset_name), None)
