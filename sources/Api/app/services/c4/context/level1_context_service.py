"""C4 Level-1 context generation and review services.

This module intentionally provides a minimal in-memory implementation so API
contracts for tasks 3.* and 4.* can be integrated before persistence layers are
fully available.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


APPROVED_RELATIONSHIP_TYPES: set[str] = {
    "uses",
    "depends_on",
    "publishes_events_to",
    "consumes_from",
    "integrates_with",
    "owned_by",
}

REVIEW_STATUSES: set[str] = {"draft", "reviewed", "approved_for_publish"}

VALID_ROLES: set[str] = {"viewer", "editor", "approver"}


class ProvenanceMetadata(BaseModel):
    """Provenance metadata attached to generated fields."""

    source_type: str
    source_path: str
    source_hash: str
    artifact_version: str
    extraction_rule: str
    confidence: float = Field(ge=0.0, le=1.0)
    last_seen: str


class Level1Relationship(BaseModel):
    """Relationship used in Level-1 context rendering."""

    source_entity_id: str
    relation_type: str
    target_entity_id: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    is_automatic: bool = True


class FieldTriplet(BaseModel):
    """Field representation with generated/override/effective values."""

    generated: Any = None
    override: Any = None
    effective: Any = None
    state: str


class ValidationSignal(BaseModel):
    """Validation signal emitted during render."""

    code: str
    message: str
    field_path: str | None = None


class Level1ContextResponse(BaseModel):
    """Response payload for Level-1 context endpoint."""

    system_id: str
    snapshot_id: str
    extracted_at: str
    review_status: str
    fields: dict[str, FieldTriplet]
    provenance: dict[str, ProvenanceMetadata]
    relationships: list[Level1Relationship]
    validation_signals: list[ValidationSignal]
    render_fingerprint: str


class OverrideRequest(BaseModel):
    """Override upsert request payload."""

    field_path: str
    value: Any
    updated_by: str
    override_reason: str


class ReviewStatusRequest(BaseModel):
    """Review status transition request payload."""

    status: str
    updated_by: str


@dataclass
class ContextSnapshot:
    """In-memory snapshot representation."""

    system_id: str
    snapshot_id: str
    extracted_at: str
    generated_fields: dict[str, Any]
    provenance: dict[str, ProvenanceMetadata]
    relationships: list[Level1Relationship]


@dataclass
class ContextOverride:
    """Field-level override state."""

    field_path: str
    value: Any
    updated_by: str
    override_reason: str
    field_updated_at: str
    status: str = "active"


@dataclass
class SystemReviewState:
    """Review state for a system."""

    status: str = "draft"
    updated_by: str = "system"
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class InMemoryContextStore:
    """In-memory adapter for snapshots, overrides, and review states."""

    def __init__(self) -> None:
        self._snapshots: dict[tuple[str, str], ContextSnapshot] = {}
        self._overrides: dict[str, dict[str, ContextOverride]] = {}
        self._review_states: dict[str, SystemReviewState] = {}
        self._seed_wps_snapshot()

    def _seed_wps_snapshot(self) -> None:
        system_id = "wps"
        snapshot_id = "wps-snap-001"
        extracted_at = "2026-02-19T00:00:00+00:00"

        generated_fields = {
            "name": "WPS",
            "owner": "platform-core",
            "domain": "Payments",
            "lifecycle": "ACTIVE",
            "tier": "Tier 1",
            "data_class": "Confidential",
        }

        provenance = {
            field_name: ProvenanceMetadata(
                source_type="service-universe",
                source_path="service-universe/wps.yaml",
                source_hash="sha256:wps-source-hash",
                artifact_version="v1",
                extraction_rule=f"rule_{field_name}",
                confidence=0.9,
                last_seen=extracted_at,
            )
            for field_name in generated_fields
        }

        relationships = [
            Level1Relationship(
                source_entity_id="wps",
                relation_type="uses",
                target_entity_id="stripe",
                description="uses payment processing",
                confidence=0.95,
                is_automatic=True,
            ),
            Level1Relationship(
                source_entity_id="wps",
                relation_type="integrates_with",
                target_entity_id="sap",
                description="integrates with ERP",
                confidence=0.85,
                is_automatic=True,
            ),
            Level1Relationship(
                source_entity_id="wps",
                relation_type="owned_by",
                target_entity_id="platform-core",
                description="owned by platform-core",
                confidence=1.0,
                is_automatic=False,
            ),
        ]

        self._snapshots[(system_id, snapshot_id)] = ContextSnapshot(
            system_id=system_id,
            snapshot_id=snapshot_id,
            extracted_at=extracted_at,
            generated_fields=generated_fields,
            provenance=provenance,
            relationships=relationships,
        )

    def get_snapshot(self, system_id: str, snapshot_id: str) -> ContextSnapshot | None:
        return self._snapshots.get((system_id, snapshot_id))

    def upsert_override(self, system_id: str, request: OverrideRequest) -> ContextOverride:
        now = datetime.now(timezone.utc).isoformat()
        if system_id not in self._overrides:
            self._overrides[system_id] = {}

        override = ContextOverride(
            field_path=request.field_path,
            value=request.value,
            updated_by=request.updated_by,
            override_reason=request.override_reason,
            field_updated_at=now,
            status="active",
        )
        self._overrides[system_id][request.field_path] = override
        return override

    def list_overrides(self, system_id: str) -> dict[str, ContextOverride]:
        return self._overrides.get(system_id, {})

    def get_review_state(self, system_id: str) -> SystemReviewState:
        if system_id not in self._review_states:
            self._review_states[system_id] = SystemReviewState()
        return self._review_states[system_id]

    def set_review_state(self, system_id: str, status: str, updated_by: str) -> SystemReviewState:
        next_state = SystemReviewState(
            status=status,
            updated_by=updated_by,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._review_states[system_id] = next_state
        return next_state


class Level1ContextService:
    """Service for deterministic Level-1 rendering and review operations."""

    def __init__(self, store: InMemoryContextStore | None = None) -> None:
        self.store = store or InMemoryContextStore()

    def render_level1_context(
        self,
        *,
        system_id: str,
        snapshot_id: str,
        min_confidence: float,
    ) -> Level1ContextResponse:
        snapshot = self.store.get_snapshot(system_id=system_id, snapshot_id=snapshot_id)
        if snapshot is None:
            raise ValueError(
                f"Snapshot '{snapshot_id}' for system '{system_id}' was not found"
            )

        if min_confidence < 0.0 or min_confidence > 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")

        validation_signals: list[ValidationSignal] = []
        relationships: list[Level1Relationship] = []

        for edge in snapshot.relationships:
            if edge.relation_type not in APPROVED_RELATIONSHIP_TYPES:
                validation_signals.append(
                    ValidationSignal(
                        code="unsupported_relationship_type",
                        message=(
                            f"Relationship '{edge.relation_type}' is not part of the approved taxonomy"
                        ),
                        field_path=(
                            f"relationships.{edge.source_entity_id}.{edge.target_entity_id}"
                        ),
                    )
                )
                continue

            if edge.is_automatic and edge.confidence < min_confidence:
                validation_signals.append(
                    ValidationSignal(
                        code="edge_gated_by_confidence",
                        message=(
                            f"Relationship '{edge.relation_type}' was gated (confidence={edge.confidence})"
                        ),
                        field_path=(
                            f"relationships.{edge.source_entity_id}.{edge.target_entity_id}"
                        ),
                    )
                )
                continue

            relationships.append(edge)

        # Stable ordering ensures deterministic output for unchanged inputs.
        relationships = sorted(
            relationships,
            key=lambda rel: (
                rel.source_entity_id,
                rel.target_entity_id,
                rel.relation_type,
                rel.description,
                rel.confidence,
            ),
        )

        overrides = self.store.list_overrides(system_id)
        fields = self._build_field_triplets(
            generated_fields=snapshot.generated_fields,
            overrides=overrides,
        )

        response = Level1ContextResponse(
            system_id=system_id,
            snapshot_id=snapshot.snapshot_id,
            extracted_at=snapshot.extracted_at,
            review_status=self.store.get_review_state(system_id).status,
            fields=fields,
            provenance={
                key: snapshot.provenance[key]
                for key in sorted(snapshot.provenance.keys())
            },
            relationships=relationships,
            validation_signals=validation_signals,
            render_fingerprint="",
        )
        response.render_fingerprint = self._fingerprint_response(response)
        return response

    def upsert_override(self, *, system_id: str, request: OverrideRequest) -> ContextOverride:
        if not request.field_path.strip():
            raise ValueError("field_path is required")
        if not request.updated_by.strip():
            raise ValueError("updated_by is required")
        if not request.override_reason.strip():
            raise ValueError("override_reason is required")

        return self.store.upsert_override(system_id, request)

    def transition_review_status(
        self, *, system_id: str, request: ReviewStatusRequest
    ) -> SystemReviewState:
        if request.status not in REVIEW_STATUSES:
            raise ValueError(
                "status must be one of: draft, reviewed, approved_for_publish"
            )
        if not request.updated_by.strip():
            raise ValueError("updated_by is required")

        current = self.store.get_review_state(system_id).status
        allowed_transitions = {
            "draft": {"reviewed"},
            "reviewed": {"draft", "approved_for_publish"},
            "approved_for_publish": {"reviewed"},
        }

        if request.status == current:
            return self.store.get_review_state(system_id)

        if request.status not in allowed_transitions[current]:
            raise ValueError(
                f"Invalid transition from '{current}' to '{request.status}'"
            )

        return self.store.set_review_state(
            system_id=system_id,
            status=request.status,
            updated_by=request.updated_by,
        )

    @staticmethod
    def _build_field_triplets(
        *, generated_fields: dict[str, Any], overrides: dict[str, ContextOverride]
    ) -> dict[str, FieldTriplet]:
        triplets: dict[str, FieldTriplet] = {}

        all_paths = sorted(set(generated_fields.keys()) | set(overrides.keys()))
        for field_path in all_paths:
            generated_value = generated_fields.get(field_path)
            override_value = overrides.get(field_path).value if field_path in overrides else None
            effective_value = override_value if field_path in overrides else generated_value

            state = "missing"
            if field_path in overrides:
                state = "overridden"
            elif generated_value is not None:
                state = "generated"

            triplets[field_path] = FieldTriplet(
                generated=generated_value,
                override=override_value,
                effective=effective_value,
                state=state,
            )

        return triplets

    @staticmethod
    def _fingerprint_response(response: Level1ContextResponse) -> str:
        payload = response.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()
