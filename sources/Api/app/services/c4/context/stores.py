"""In-memory stores for canonical snapshots and field overrides."""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical_models import CanonicalSnapshot, FieldOverride, OverrideStatus


@dataclass
class CanonicalSnapshotStore:
    """Append-only snapshot store keyed by system and snapshot IDs."""

    _snapshots: dict[str, list[CanonicalSnapshot]] = field(default_factory=dict)

    def save(self, snapshot: CanonicalSnapshot) -> CanonicalSnapshot:
        snapshots = self._snapshots.setdefault(snapshot.system_id, [])
        snapshots.append(snapshot)
        return snapshot

    def list_by_system(self, system_id: str) -> list[CanonicalSnapshot]:
        return list(self._snapshots.get(system_id, []))

    def get(self, system_id: str, snapshot_id: str) -> CanonicalSnapshot | None:
        for snapshot in self._snapshots.get(system_id, []):
            if snapshot.snapshot_id == snapshot_id:
                return snapshot
        return None


@dataclass
class OverrideStore:
    """Field override store keyed by (system_id, field_path)."""

    _overrides: dict[tuple[str, str], FieldOverride] = field(default_factory=dict)

    def upsert(self, override: FieldOverride) -> FieldOverride:
        key = (override.system_id, override.field_path)
        existing = self._overrides.get(key)
        if existing:
            existing.status = OverrideStatus.SUPERSEDED
        self._overrides[key] = override
        return override

    def get(self, system_id: str, field_path: str) -> FieldOverride | None:
        return self._overrides.get((system_id, field_path))

    def list_by_system(self, system_id: str) -> list[FieldOverride]:
        return [override for (sid, _), override in self._overrides.items() if sid == system_id]

