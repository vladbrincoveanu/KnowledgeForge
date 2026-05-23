"""Unit tests for ContainerManager._apply_verdicts().

Verifies that LLM verdicts (`discard`, `merge`) actually mutate the
container set: discarded containers are removed, merged containers fold
into their target, and inbound edges are redirected or dropped.
"""

import json
import pytest
from pathlib import Path
import tempfile
from unittest.mock import MagicMock

from app.services.c4.containers.container_manager import ContainerManager


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def make_manager(temp_repo: Path, containers: dict) -> ContainerManager:
    """Build a ContainerManager with a pre-populated containers dict."""
    cm = ContainerManager.__new__(ContainerManager)
    cm.repo_path = temp_repo
    cm.llm_manager = None
    cm.containers = containers
    return cm


def _container(name: str, **fields) -> dict:
    base = {
        "name": name,
        "path": f"services/{name}",
        "container_type": "Service",
        "technology": "Unknown",
        "protocol": "HTTP",
        "description": "",
        "dependencies_internal": [],
        "relationships": [],
    }
    base.update(fields)
    return base


class TestDiscardVerdict:
    def test_discard_above_threshold_removes_container(self, temp_repo):
        cm = make_manager(temp_repo, {
            "api": _container("api"),
            "junk": _container("junk", llm_verdict="discard", llm_confidence=0.9),
        })
        stats = cm._apply_verdicts()
        assert "junk" not in cm.containers
        assert "api" in cm.containers
        assert stats["discarded"] == 1

    def test_discard_below_threshold_keeps_container(self, temp_repo):
        cm = make_manager(temp_repo, {
            "borderline": _container(
                "borderline", llm_verdict="discard", llm_confidence=0.3
            ),
        })
        cm._apply_verdicts()
        assert "borderline" in cm.containers

    def test_inbound_edges_to_discarded_dropped(self, temp_repo):
        cm = make_manager(temp_repo, {
            "api": _container("api", relationships=[
                {"from": "api", "to": "junk", "type": "uses", "protocol": "HTTP"},
                {"from": "api", "to": "db", "type": "uses", "protocol": "PostgreSQL"},
            ]),
            "junk": _container("junk", llm_verdict="discard", llm_confidence=0.9),
            "db": _container("db"),
        })
        cm._apply_verdicts()
        api_targets = {r["to"] for r in cm.containers["api"]["relationships"]}
        assert api_targets == {"db"}

    def test_dependencies_internal_to_discarded_dropped(self, temp_repo):
        cm = make_manager(temp_repo, {
            "api": _container("api", dependencies_internal=["junk", "db"]),
            "junk": _container("junk", llm_verdict="discard", llm_confidence=0.9),
            "db": _container("db"),
        })
        cm._apply_verdicts()
        assert cm.containers["api"]["dependencies_internal"] == ["db"]


class TestMergeVerdict:
    def test_merge_above_threshold_removes_source(self, temp_repo):
        cm = make_manager(temp_repo, {
            "api-v1": _container(
                "api-v1", llm_verdict="merge",
                llm_merge_into="api", llm_confidence=0.85,
            ),
            "api": _container("api"),
        })
        stats = cm._apply_verdicts()
        assert "api-v1" not in cm.containers
        assert "api" in cm.containers
        assert stats["merged"] == 1

    def test_merge_folds_relationships_into_target(self, temp_repo):
        rel = {"from": "api-v1", "to": "db", "type": "uses", "protocol": "PostgreSQL"}
        cm = make_manager(temp_repo, {
            "api-v1": _container(
                "api-v1", llm_verdict="merge",
                llm_merge_into="api", llm_confidence=0.85,
                relationships=[rel],
            ),
            "api": _container("api"),
            "db": _container("db"),
        })
        cm._apply_verdicts()
        api_rels = cm.containers["api"]["relationships"]
        assert any(r.get("to") == "db" for r in api_rels)

    def test_inbound_edges_redirected_to_merge_target(self, temp_repo):
        cm = make_manager(temp_repo, {
            "client": _container("client", relationships=[
                {"from": "client", "to": "api-v1", "type": "uses", "protocol": "HTTP"},
            ]),
            "api-v1": _container(
                "api-v1", llm_verdict="merge",
                llm_merge_into="api", llm_confidence=0.85,
            ),
            "api": _container("api"),
        })
        cm._apply_verdicts()
        targets = {r["to"] for r in cm.containers["client"]["relationships"]}
        assert targets == {"api"}

    def test_unresolvable_target_leaves_source_intact(self, temp_repo):
        cm = make_manager(temp_repo, {
            "orphan": _container(
                "orphan", llm_verdict="merge",
                llm_merge_into="nonexistent", llm_confidence=0.85,
            ),
        })
        cm._apply_verdicts()
        assert "orphan" in cm.containers

    def test_merge_chain_resolves_to_final_target(self, temp_repo):
        """A→B→C should leave A and B gone, C with everything."""
        cm = make_manager(temp_repo, {
            "a": _container(
                "a", llm_verdict="merge",
                llm_merge_into="b", llm_confidence=0.85,
                relationships=[{"from": "a", "to": "db", "type": "uses", "protocol": "HTTP"}],
            ),
            "b": _container(
                "b", llm_verdict="merge",
                llm_merge_into="c", llm_confidence=0.85,
            ),
            "c": _container("c"),
            "db": _container("db"),
        })
        cm._apply_verdicts()
        assert "a" not in cm.containers
        assert "b" not in cm.containers
        assert "c" in cm.containers
        c_targets = {r["to"] for r in cm.containers["c"]["relationships"]}
        assert "db" in c_targets

    def test_merge_cycle_falls_back_to_discard(self, temp_repo):
        """A→B→A should not loop forever; both get treated as discard."""
        cm = make_manager(temp_repo, {
            "a": _container(
                "a", llm_verdict="merge",
                llm_merge_into="b", llm_confidence=0.85,
            ),
            "b": _container(
                "b", llm_verdict="merge",
                llm_merge_into="a", llm_confidence=0.85,
            ),
            "survivor": _container("survivor"),
        })
        cm._apply_verdicts()
        # Both ends of the cycle removed, survivor unaffected
        assert "a" not in cm.containers
        assert "b" not in cm.containers
        assert "survivor" in cm.containers


class TestKeepVerdict:
    def test_keep_verdict_unchanged(self, temp_repo):
        cm = make_manager(temp_repo, {
            "api": _container("api", llm_verdict="keep", llm_confidence=0.9),
        })
        cm._apply_verdicts()
        assert "api" in cm.containers

    def test_no_verdict_unchanged(self, temp_repo):
        """Containers that never reached the LLM (no verdict) must survive."""
        cm = make_manager(temp_repo, {
            "untouched": _container("untouched"),
        })
        cm._apply_verdicts()
        assert "untouched" in cm.containers


class TestSanityFalsePositives:
    def test_high_confidence_fp_removes_container(self, temp_repo):
        cm = make_manager(temp_repo, {
            "api": _container("api"),
            "tool": _container("tool"),
        })
        removed = cm._apply_sanity_false_positives([
            {"name": "tool", "reason": "code generator", "confidence": 0.9},
        ])
        assert removed == 1
        assert "tool" not in cm.containers
        assert "api" in cm.containers

    def test_low_confidence_fp_only_marks(self, temp_repo):
        cm = make_manager(temp_repo, {
            "borderline": _container("borderline"),
        })
        removed = cm._apply_sanity_false_positives([
            {"name": "borderline", "reason": "unsure", "confidence": 0.4},
        ])
        assert removed == 0
        assert "borderline" in cm.containers
        assert cm.containers["borderline"]["sanity_flag"]["verdict"] == "false_positive"

    def test_inbound_edges_to_removed_dropped(self, temp_repo):
        cm = make_manager(temp_repo, {
            "client": _container("client", relationships=[
                {"from": "client", "to": "junk", "type": "uses"},
                {"from": "client", "to": "api", "type": "uses"},
            ]),
            "junk": _container("junk"),
            "api": _container("api"),
        })
        cm._apply_sanity_false_positives([
            {"name": "junk", "reason": "build tool", "confidence": 0.9},
        ])
        targets = {r["to"] for r in cm.containers["client"]["relationships"]}
        assert targets == {"api"}

    def test_unknown_name_ignored(self, temp_repo):
        cm = make_manager(temp_repo, {"api": _container("api")})
        removed = cm._apply_sanity_false_positives([
            {"name": "ghost", "reason": "x", "confidence": 0.99},
        ])
        assert removed == 0
        assert "api" in cm.containers


class TestEnrichContainersWithLLMIntegration:
    """End-to-end: enrich_containers_with_llm() must chunk all candidates
    AND remove discarded ones; nothing should leak through to the caller."""

    def test_full_pipeline_drops_discarded(self, temp_repo):
        from app.services.c4.containers.llm_enrichment import (
            MAX_CONTAINERS_PER_BATCH,
        )

        # Seed a candidate set bigger than one chunk so we exercise both
        # the chunking loop AND the verdict enforcement.
        n = MAX_CONTAINERS_PER_BATCH + 3
        keep_names = [f"svc-{i}" for i in range(n - 2)]
        discard_names = ["junk-1", "junk-2"]
        all_names = keep_names + discard_names

        cm = make_manager(temp_repo, {
            name: _container(name) for name in all_names
        })

        def respond(prompt, **kwargs):
            # Return a verdict for every name that appears in this chunk's prompt
            response_containers = []
            for name in all_names:
                if f'"{name}"' in prompt:
                    if name in discard_names:
                        response_containers.append({
                            "name": name, "verdict": "discard",
                            "container_type": None, "technology": None,
                            "protocol": None, "description": None,
                            "confidence": 0.9, "notes": "build helper",
                        })
                    else:
                        response_containers.append({
                            "name": name, "verdict": "keep",
                            "container_type": "Microservice",
                            "technology": "Python",
                            "protocol": "HTTP",
                            "description": "Service.",
                            "confidence": 0.85, "notes": "",
                        })
            return json.dumps({
                "containers": response_containers,
                "inferred_relationships": [],
            })

        mock_llm = MagicMock()
        mock_llm.generate_text.side_effect = respond
        mock_llm.timeout = 30
        cm.llm_manager = mock_llm

        stats = cm.enrich_containers_with_llm()

        # Every kept service survives; every discard is gone.
        for name in keep_names:
            assert name in cm.containers
        for name in discard_names:
            assert name not in cm.containers

        # And the stats reflect the enforcement
        assert stats["verdicts_enforced"]["discarded"] == len(discard_names)
        assert stats["verdicts_enforced"]["merged"] == 0
