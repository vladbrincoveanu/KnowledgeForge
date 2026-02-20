"""Tests for deterministic C4 Level-1 context generation behavior."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.c4.context.level1_context_service import (
    InMemoryContextStore,
    Level1ContextService,
    Level1Relationship,
)


def test_render_requires_explicit_snapshot_version() -> None:
    service = Level1ContextService()

    result = service.render_level1_context(
        system_id="wps", snapshot_id="wps-snap-001", min_confidence=0.8
    )

    assert result.system_id == "wps"
    assert result.snapshot_id == "wps-snap-001"


def test_enforces_relationship_taxonomy_and_emits_validation_signal() -> None:
    store = InMemoryContextStore()
    snapshot = store.get_snapshot("wps", "wps-snap-001")
    assert snapshot is not None
    snapshot.relationships.append(
        Level1Relationship(
            source_entity_id="wps",
            relation_type="calls",  # Unsupported taxonomy
            target_entity_id="unknown-service",
            description="calls unknown-service",
            confidence=0.9,
            is_automatic=True,
        )
    )

    service = Level1ContextService(store=store)
    result = service.render_level1_context(
        system_id="wps", snapshot_id="wps-snap-001", min_confidence=0.8
    )

    assert all(rel.relation_type != "calls" for rel in result.relationships)
    assert any(
        signal.code == "unsupported_relationship_type"
        for signal in result.validation_signals
    )


def test_confidence_threshold_gates_low_confidence_automatic_edges() -> None:
    store = InMemoryContextStore()
    snapshot = store.get_snapshot("wps", "wps-snap-001")
    assert snapshot is not None
    snapshot.relationships.append(
        Level1Relationship(
            source_entity_id="wps",
            relation_type="uses",
            target_entity_id="low-confidence-api",
            description="uses low-confidence-api",
            confidence=0.4,
            is_automatic=True,
        )
    )

    service = Level1ContextService(store=store)
    result = service.render_level1_context(
        system_id="wps", snapshot_id="wps-snap-001", min_confidence=0.8
    )

    assert all(rel.target_entity_id != "low-confidence-api" for rel in result.relationships)
    assert any(
        signal.code == "edge_gated_by_confidence" for signal in result.validation_signals
    )


def test_render_is_deterministic_for_unchanged_inputs() -> None:
    service = Level1ContextService()

    first = service.render_level1_context(
        system_id="wps", snapshot_id="wps-snap-001", min_confidence=0.8
    )
    second = service.render_level1_context(
        system_id="wps", snapshot_id="wps-snap-001", min_confidence=0.8
    )

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.render_fingerprint == second.render_fingerprint


def test_wps_relationships_match_golden_fixture() -> None:
    service = Level1ContextService()
    result = service.render_level1_context(
        system_id="wps", snapshot_id="wps-snap-001", min_confidence=0.8
    )

    fixture_path = (
        Path(__file__).resolve().parents[4]
        / "fixtures"
        / "c4"
        / "wps_level1_relationships_golden.json"
    )

    expected = json.loads(fixture_path.read_text())
    actual = [relationship.model_dump(mode="json") for relationship in result.relationships]

    assert actual == expected
