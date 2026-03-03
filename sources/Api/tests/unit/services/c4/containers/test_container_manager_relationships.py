"""Unit tests for ContainerManager.build_container_relationships()."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

from app.services.c4.containers.container_manager import ContainerManager


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def make_manager(temp_repo: Path, containers: dict) -> ContainerManager:
    """Build a ContainerManager with a pre-populated containers dict, skipping real detection."""
    cm = ContainerManager.__new__(ContainerManager)
    cm.repo_path = temp_repo
    cm.llm_manager = None
    cm.containers = containers
    return cm


class TestBuildContainerRelationshipsPhase1:
    def test_detector_relationships_are_harvested(self, temp_repo):
        cm = make_manager(temp_repo, {
            "api": {
                "name": "api",
                "relationships": [
                    {"from": "api", "to": "db", "type": "uses", "protocol": "PostgreSQL", "source": "compose"}
                ],
                "dependencies_internal": [],
            },
            "db": {"name": "db", "relationships": [], "dependencies_internal": []},
        })
        rels = cm.build_container_relationships()
        assert len(rels) == 1
        assert rels[0]["from"] == "api"
        assert rels[0]["to"] == "db"
        assert rels[0]["protocol"] == "PostgreSQL"
        assert rels[0]["source"] == "compose"

    def test_dedup_by_from_to_type_protocol(self, temp_repo):
        """Duplicate (from, to, type, protocol) tuples must be de-duplicated."""
        dup_rel = {"from": "api", "to": "db", "type": "uses", "protocol": "PostgreSQL", "source": "compose"}
        cm = make_manager(temp_repo, {
            "api": {
                "name": "api",
                "relationships": [dup_rel, dup_rel],
                "dependencies_internal": [],
            },
            "db": {"name": "db", "relationships": [], "dependencies_internal": []},
        })
        rels = cm.build_container_relationships()
        assert len(rels) == 1

    def test_self_reference_discarded(self, temp_repo):
        cm = make_manager(temp_repo, {
            "api": {
                "name": "api",
                "relationships": [
                    {"from": "api", "to": "api", "type": "uses", "protocol": "HTTP", "source": "compose"}
                ],
                "dependencies_internal": [],
            },
        })
        rels = cm.build_container_relationships()
        assert rels == []

    def test_unresolved_helm_rel_excluded(self, temp_repo):
        """Relationships with _unresolved=True that can't be slug-matched are discarded."""
        cm = make_manager(temp_repo, {
            "svc": {
                "name": "svc",
                "relationships": [
                    {
                        "from": "svc", "to": "http://some-external-thing",
                        "type": "uses", "protocol": "HTTP",
                        "source": "helm", "_unresolved": True,
                    }
                ],
                "dependencies_internal": [],
            },
        })
        rels = cm.build_container_relationships()
        assert rels == []

    def test_unresolved_helm_rel_resolved_when_name_matches(self, temp_repo):
        """_unresolved rel is kept when 'to' resolves to a known container."""
        cm = make_manager(temp_repo, {
            "frontend": {
                "name": "frontend",
                "relationships": [
                    {
                        "from": "frontend", "to": "backend",
                        "type": "uses", "protocol": "HTTP",
                        "source": "helm", "_unresolved": True,
                    }
                ],
                "dependencies_internal": [],
            },
            "backend": {"name": "backend", "relationships": [], "dependencies_internal": []},
        })
        rels = cm.build_container_relationships()
        assert len(rels) == 1
        assert rels[0]["to"] == "backend"
        assert "_unresolved" not in rels[0]


class TestBuildContainerRelationshipsPhase2:
    def test_legacy_fallback_used_when_no_detector_rels(self, temp_repo):
        """Phase 2: containers without detector rels fall back to dependencies_internal."""
        cm = make_manager(temp_repo, {
            "api": {
                "name": "api",
                "protocol": "HTTP",
                "dependencies_internal": ["db"],
            },
            "db": {"name": "db", "dependencies_internal": []},
        })
        rels = cm.build_container_relationships()
        assert len(rels) == 1
        assert rels[0]["from"] == "api"
        assert rels[0]["to"] == "db"
        assert rels[0]["source"] == "runtime"

    def test_legacy_fallback_skipped_when_detector_rels_exist(self, temp_repo):
        """Phase 2 must be skipped for containers that already have Phase 1 rels."""
        cm = make_manager(temp_repo, {
            "api": {
                "name": "api",
                "protocol": "gRPC",
                "relationships": [
                    {"from": "api", "to": "db", "type": "uses", "protocol": "PostgreSQL", "source": "compose"}
                ],
                "dependencies_internal": ["cache"],  # should NOT produce a second rel
            },
            "db": {"name": "db", "relationships": [], "dependencies_internal": []},
            "cache": {"name": "cache", "relationships": [], "dependencies_internal": []},
        })
        rels = cm.build_container_relationships()
        # Only the explicit detector rel, no fallback for api→cache
        targets = {r["to"] for r in rels}
        assert "db" in targets
        assert "cache" not in targets

    def test_legacy_dep_to_unknown_container_excluded(self, temp_repo):
        cm = make_manager(temp_repo, {
            "svc": {
                "name": "svc",
                "protocol": "HTTP",
                "dependencies_internal": ["nonexistent"],
            },
        })
        rels = cm.build_container_relationships()
        assert rels == []


class TestRelationshipFieldsIntegrity:
    def test_result_has_required_fields(self, temp_repo):
        cm = make_manager(temp_repo, {
            "a": {
                "name": "a",
                "relationships": [
                    {"from": "a", "to": "b", "type": "uses", "protocol": "HTTP", "source": "compose"}
                ],
                "dependencies_internal": [],
            },
            "b": {"name": "b", "relationships": [], "dependencies_internal": []},
        })
        rels = cm.build_container_relationships()
        assert len(rels) == 1
        rel = rels[0]
        for field in ("from", "to", "type", "protocol", "source"):
            assert field in rel

    def test_internal_unresolved_key_stripped_from_output(self, temp_repo):
        cm = make_manager(temp_repo, {
            "svc": {
                "name": "svc",
                "relationships": [
                    {
                        "from": "svc", "to": "other",
                        "type": "uses", "protocol": "HTTP",
                        "source": "helm", "_unresolved": True,
                    }
                ],
                "dependencies_internal": [],
            },
            "other": {"name": "other", "relationships": [], "dependencies_internal": []},
        })
        rels = cm.build_container_relationships()
        if rels:
            assert "_unresolved" not in rels[0]
