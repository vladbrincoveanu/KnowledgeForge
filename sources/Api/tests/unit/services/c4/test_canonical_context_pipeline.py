"""Unit tests for canonical context extraction and merge pipeline."""

from datetime import datetime, timedelta, timezone

from app.services.c4.context.canonical_models import (
    CanonicalFieldValue,
    FieldCandidate,
    FieldOverride,
    OverrideStatus,
    deterministic_id,
)
from app.services.c4.context.merge_engine import ContextMergeEngine
from app.services.c4.context.precedence import FieldPrecedenceResolver
from app.services.c4.context.stores import CanonicalSnapshotStore, OverrideStore


def test_deterministic_id_is_stable():
    left = deterministic_id("system", "WPS")
    right = deterministic_id("system", "WPS")
    assert left == right
    assert len(left) == 16


def test_precedence_prefers_higher_ranked_source():
    resolver = FieldPrecedenceResolver()
    now = datetime.now(timezone.utc)
    candidates = [
        FieldCandidate(
            field_name="owner",
            value="heuristic-team",
            source_type="heuristic",
            source_path="a",
            extraction_rule="h",
            confidence=0.9,
            last_seen=now,
        ),
        FieldCandidate(
            field_name="owner",
            value="codeowners/team-x",
            source_type="codeowners",
            source_path="CODEOWNERS",
            extraction_rule="codeowners:first_team",
            confidence=0.7,
            last_seen=now - timedelta(minutes=5),
        ),
    ]
    resolved = resolver.resolve("owner", candidates)
    assert resolved.value == "codeowners/team-x"
    assert resolved.provenance[0].source_type == "codeowners"


def test_unknown_state_when_confidence_below_threshold():
    resolver = FieldPrecedenceResolver(unknown_confidence_threshold=0.8)
    candidate = FieldCandidate(
        field_name="domain",
        value="payments",
        source_type="heuristic",
        source_path="README.md",
        extraction_rule="readme:domain_pattern",
        confidence=0.6,
    )
    resolved = resolver.resolve("domain", [candidate])
    assert resolved.value == "unknown"
    assert resolved.confidence == 0.6


def test_provenance_contains_required_fields():
    resolver = FieldPrecedenceResolver()
    candidate = FieldCandidate(
        field_name="compliance_flags",
        value=["pci"],
        source_type="compliance_artifact",
        source_path="compliance.json",
        source_hash="abc123",
        artifact_version="v1",
        extraction_rule="compliance_file:flags",
        confidence=0.95,
    )
    resolved = resolver.resolve("compliance_flags", [candidate])
    provenance = resolved.provenance[0]
    assert provenance.source_hash == "abc123"
    assert provenance.artifact_version == "v1"
    assert provenance.extraction_rule == "compliance_file:flags"


def test_snapshot_store_persists_versions():
    store = CanonicalSnapshotStore()
    from app.services.c4.context.canonical_models import CanonicalSnapshot

    system_id = "sys-1"
    first = CanonicalSnapshot(
        system_id=system_id,
        snapshot_id="snap-1",
        extracted_at=datetime.now(timezone.utc),
        entities=[],
        relationships=[],
    )
    second = CanonicalSnapshot(
        system_id=system_id,
        snapshot_id="snap-2",
        extracted_at=datetime.now(timezone.utc),
        entities=[],
        relationships=[],
    )
    store.save(first)
    store.save(second)
    snapshots = store.list_by_system(system_id)
    assert len(snapshots) == 2
    assert store.get(system_id, "snap-2") is not None


def test_override_store_and_merge_effective_value():
    override_store = OverrideStore()
    engine = ContextMergeEngine()

    system_id = "sys-2"
    field_path = "system.owner"
    override = FieldOverride(
        system_id=system_id,
        field_path=field_path,
        value="platform-team",
        updated_by="sme.user",
        override_reason="validated with org chart",
    )
    override_store.upsert(override)

    generated = CanonicalFieldValue(value="codeowners/team-x", confidence=0.9, provenance=[])
    merged = engine.merge_field(generated, override_store.get(system_id, field_path))
    assert merged.state == "overridden"
    assert merged.effective == "platform-team"


def test_stale_override_detection_on_better_generated_source():
    engine = ContextMergeEngine()
    override = FieldOverride(
        system_id="sys-3",
        field_path="system.owner",
        value="manual-owner",
        status=OverrideStatus.ACTIVE,
        last_generated_value="old-owner",
        last_generated_confidence=0.5,
        last_generated_source_rank=4,
    )
    generated = CanonicalFieldValue(value="new-owner", confidence=0.8, provenance=[])
    updated = engine.update_override_status(
        override=override,
        generated_value=generated,
        generated_source_rank=1,
    )
    assert updated.status == OverrideStatus.STALE
    assert updated.needs_review is True

