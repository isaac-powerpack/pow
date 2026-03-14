"""AssetProfile model — represents the data in an asset-profile.toml file."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List


@dataclass
class AssetEntry:
    """A single downloadable asset pack within a group."""

    name: str
    status: str
    size_bytes: int
    aria2_gid: str
    archive_files: List[str]
    extract_info_file: str

    @classmethod
    def from_dict(cls, data: dict) -> AssetEntry:
        return cls(
            name=data["name"],
            status=data.get("status", ""),
            size_bytes=data.get("size_bytes", 0),
            aria2_gid=data.get("aria2_gid", ""),
            archive_files=data.get("archive_files", []),
            extract_info_file=data.get("extract_info_file", ""),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "size_bytes": self.size_bytes,
            "aria2_gid": self.aria2_gid,
            "archive_files": self.archive_files,
            "extract_info_file": self.extract_info_file,
        }


@dataclass
class AssetGroup:
    """A named group containing one or more asset entries."""

    name: str
    assets: List[AssetEntry] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> AssetGroup:
        assets = [AssetEntry.from_dict(a) for a in data.get("asset", [])]
        return cls(name=data["name"], assets=assets)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "asset": [a.to_dict() for a in self.assets],
        }


@dataclass
class ProfileMeta:
    """Metadata header stored under [profile] in asset-profile.toml."""

    schema_version: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_dict(cls, data: dict) -> ProfileMeta:
        return cls(
            schema_version=data.get("schema_version", "0.0.0"),
            created_at=data.get("created_at", datetime.now(timezone.utc)),
            updated_at=data.get("updated_at", datetime.now(timezone.utc)),
        )

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "schema_version": self.schema_version,
        }


@dataclass
class AssetProfile:
    """
    In-memory representation of an asset-profile.toml file.

    File structure
    --------------
    [profile]
      created_at, updated_at, schema_version

    [[group]]
      name = "..."
      [[group.asset]]
        name, status, size_bytes, aria2_gid, archive_files, extract_info_file
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

    def get_group(self, name: str) -> AssetGroup | None:
        """Return the group with the given name, or None."""
        return next((g for g in self.groups if g.name == name), None)

    def get_asset(self, group_name: str, asset_name: str) -> AssetEntry | None:
        """Return a specific asset entry, or None if not found."""
        group = self.get_group(group_name)
        if group is None:
            return None
        return next((a for a in group.assets if a.name == asset_name), None)
