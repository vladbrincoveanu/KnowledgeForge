"""Unit tests for containers/llm_enrichment.py."""

import json
import pytest
from unittest.mock import MagicMock, patch

from app.services.c4.containers.llm_enrichment import (
    build_evidence_bundle,
    build_enrichment_prompt,
    parse_llm_enrichment_response,
    apply_enrichments,
    enrich_containers,
    _infer_signal_type,
    _should_update_field,
    _GENERIC_CONTAINER_TYPES,
    _GENERIC_TECHNOLOGIES,
    _SYSTEM_PROMPT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_containers():
    return {
        "api": {
            "name": "api",
            "container_type": "Service",
            "technology": "Unknown",
            "protocol": "HTTP",
            "path": "services/api",
            "deployment": None,
            "description": "",
            "dependencies_internal": ["db"],
            "relationships": [],
        },
        "db": {
            "name": "db",
            "container_type": "PostgreSQL Database",
            "technology": "postgres",
            "protocol": "N/A",
            "path": "docker-compose.yml",
            "deployment": None,
            "description": "Postgres database.",
            "dependencies_internal": [],
            "relationships": [],
        },
    }


@pytest.fixture
def simple_relationships():
    return [
        {
            "from": "api", "to": "db",
            "type": "uses", "protocol": "PostgreSQL", "source": "compose",
        }
    ]


@pytest.fixture
def valid_llm_result():
    return {
        "containers": [
            {
                "name": "api",
                "verdict": "keep",
                "container_type": "ServerSideWebApp",
                "technology": "Python/FastAPI",
                "protocol": "HTTP",
                "description": "REST API serving user requests backed by PostgreSQL.",
                "confidence": 0.88,
                "notes": "FastAPI service; depends on db.",
            },
            {
                "name": "db",
                "verdict": "keep",
                "container_type": "Database",
                "technology": "PostgreSQL",
                "protocol": "PostgreSQL",
                "description": "Primary PostgreSQL datastore.",
                "confidence": 0.95,
                "notes": "Confirmed postgres image.",
            },
        ],
        "inferred_relationships": [
            {
                "from": "api", "to": "db",
                "type": "uses", "protocol": "PostgreSQL", "port": "5432",
                "description": "api persists data in db",
                "confidence": 0.9,
            }
        ],
    }


# ---------------------------------------------------------------------------
# _infer_signal_type
# ---------------------------------------------------------------------------

class TestInferSignalType:
    def test_terraform_deployment(self):
        assert _infer_signal_type({"deployment": "Terraform"}) == "terraform-resource"

    def test_helm_deployment(self):
        assert _infer_signal_type({"deployment": "Helm"}) == "helm-chart"

    def test_gitops_deployment(self):
        assert _infer_signal_type({"deployment": "GitOps"}) == "helm-chart"

    def test_docker_image_technology(self):
        result = _infer_signal_type({"technology": "confluentinc/cp-kafka", "deployment": ""})
        assert result == "docker-compose-service"

    def test_simple_image_tech(self):
        result = _infer_signal_type({"technology": "postgres", "deployment": ""})
        # "postgres" has no "/" and no ":", so it falls through to filesystem-structure
        assert result == "filesystem-structure"

    def test_unknown_falls_back_to_filesystem(self):
        assert _infer_signal_type({}) == "filesystem-structure"


# ---------------------------------------------------------------------------
# build_evidence_bundle
# ---------------------------------------------------------------------------

class TestBuildEvidenceBundle:
    def test_returns_dict_with_required_keys(self, simple_containers, simple_relationships):
        bundle = build_evidence_bundle(simple_containers, simple_relationships)
        assert "repo_context" in bundle
        assert "container_signals" in bundle
        assert "relationship_signals" in bundle

    def test_container_count_matches(self, simple_containers, simple_relationships):
        bundle = build_evidence_bundle(simple_containers, simple_relationships)
        assert bundle["repo_context"]["total_containers"] == 2
        assert len(bundle["container_signals"]) == 2

    def test_container_signal_has_name_and_signals(self, simple_containers, simple_relationships):
        bundle = build_evidence_bundle(simple_containers, simple_relationships)
        for cs in bundle["container_signals"]:
            assert "name" in cs
            assert "signals" in cs
            assert len(cs["signals"]) >= 1

    def test_relationship_signals_included(self, simple_containers, simple_relationships):
        bundle = build_evidence_bundle(simple_containers, simple_relationships)
        assert len(bundle["relationship_signals"]) == 1
        rs = bundle["relationship_signals"][0]
        assert rs["from"] == "api"
        assert rs["to"] == "db"

    def test_empty_containers_returns_valid_bundle(self):
        bundle = build_evidence_bundle({}, [])
        assert bundle["repo_context"]["total_containers"] == 0
        assert bundle["container_signals"] == []
        assert bundle["relationship_signals"] == []

    def test_relationship_signals_only_include_known_containers(self, simple_containers):
        rels = [
            {"from": "api", "to": "unknown-service", "type": "uses", "protocol": "HTTP"},
        ]
        bundle = build_evidence_bundle(simple_containers, rels)
        # Relationship is still included (filter is loose at bundle stage)
        assert len(bundle["relationship_signals"]) == 1

    def test_existing_field_captured(self, simple_containers, simple_relationships):
        bundle = build_evidence_bundle(simple_containers, simple_relationships)
        api_signal = next(c for c in bundle["container_signals"] if c["name"] == "api")
        assert api_signal["existing"]["type"] == "Service"


# ---------------------------------------------------------------------------
# build_enrichment_prompt
# ---------------------------------------------------------------------------

class TestBuildEnrichmentPrompt:
    def test_prompt_contains_system_context(self, simple_containers, simple_relationships):
        bundle = build_evidence_bundle(simple_containers, simple_relationships)
        prompt = build_enrichment_prompt(bundle)
        assert "C4 CONTAINER DEFINITION" in prompt
        assert "YOUR TASK" in prompt

    def test_prompt_contains_both_few_shot_examples(self, simple_containers, simple_relationships):
        bundle = build_evidence_bundle(simple_containers, simple_relationships)
        prompt = build_enrichment_prompt(bundle)
        assert "Example 1" in prompt
        assert "Example 2" in prompt

    def test_prompt_contains_evidence_bundle(self, simple_containers, simple_relationships):
        bundle = build_evidence_bundle(simple_containers, simple_relationships)
        prompt = build_enrichment_prompt(bundle)
        # container names should appear in the evidence section
        assert '"api"' in prompt
        assert '"db"' in prompt

    def test_prompt_is_a_string(self, simple_containers, simple_relationships):
        bundle = build_evidence_bundle(simple_containers, simple_relationships)
        assert isinstance(build_enrichment_prompt(bundle), str)

    def test_system_prompt_constant_present(self):
        assert "container" in _SYSTEM_PROMPT.lower()
        assert "discard" in _SYSTEM_PROMPT.lower()
        assert "OUTPUT SCHEMA" in _SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# parse_llm_enrichment_response
# ---------------------------------------------------------------------------

class TestParseLlmEnrichmentResponse:
    def test_valid_json_string(self, valid_llm_result):
        raw = json.dumps(valid_llm_result)
        result = parse_llm_enrichment_response(raw)
        assert result is not None
        assert len(result["containers"]) == 2

    def test_json_wrapped_in_markdown_fences(self, valid_llm_result):
        raw = f"```json\n{json.dumps(valid_llm_result)}\n```"
        result = parse_llm_enrichment_response(raw)
        assert result is not None
        assert "containers" in result

    def test_json_with_plain_backticks(self, valid_llm_result):
        raw = f"```\n{json.dumps(valid_llm_result)}\n```"
        result = parse_llm_enrichment_response(raw)
        assert result is not None

    def test_json_embedded_in_text(self, valid_llm_result):
        raw = f"Here is my analysis:\n{json.dumps(valid_llm_result)}\nDone."
        result = parse_llm_enrichment_response(raw)
        assert result is not None
        assert "containers" in result

    def test_none_input_returns_none(self):
        assert parse_llm_enrichment_response(None) is None

    def test_empty_string_returns_none(self):
        assert parse_llm_enrichment_response("") is None

    def test_invalid_json_returns_none(self):
        assert parse_llm_enrichment_response("not json at all") is None

    def test_json_without_containers_key_returns_none(self):
        raw = json.dumps({"something_else": []})
        assert parse_llm_enrichment_response(raw) is None

    def test_containers_not_a_list_returns_none(self):
        raw = json.dumps({"containers": "bad"})
        assert parse_llm_enrichment_response(raw) is None

    def test_extra_text_before_json(self, valid_llm_result):
        raw = "I think this is correct:\n\n" + json.dumps(valid_llm_result)
        result = parse_llm_enrichment_response(raw)
        assert result is not None


# ---------------------------------------------------------------------------
# apply_enrichments
# ---------------------------------------------------------------------------

class TestApplyEnrichmentsKeep:
    def test_generic_container_type_updated(self, simple_containers, simple_relationships, valid_llm_result):
        apply_enrichments(simple_containers, simple_relationships, valid_llm_result)
        assert simple_containers["api"]["container_type"] == "ServerSideWebApp"

    def test_unknown_technology_updated(self, simple_containers, simple_relationships, valid_llm_result):
        apply_enrichments(simple_containers, simple_relationships, valid_llm_result)
        assert simple_containers["api"]["technology"] == "Python/FastAPI"

    def test_empty_description_filled(self, simple_containers, simple_relationships, valid_llm_result):
        apply_enrichments(simple_containers, simple_relationships, valid_llm_result)
        assert "REST API" in simple_containers["api"]["description"]

    def test_llm_enriched_flag_set(self, simple_containers, simple_relationships, valid_llm_result):
        apply_enrichments(simple_containers, simple_relationships, valid_llm_result)
        assert simple_containers["api"]["llm_enriched"] is True

    def test_llm_verdict_keep(self, simple_containers, simple_relationships, valid_llm_result):
        apply_enrichments(simple_containers, simple_relationships, valid_llm_result)
        assert simple_containers["api"]["llm_verdict"] == "keep"

    def test_confident_field_not_overwritten(self, simple_containers, simple_relationships, valid_llm_result):
        # db has a specific, non-generic container_type already
        simple_containers["db"]["container_type"] = "PostgreSQL Database"
        apply_enrichments(simple_containers, simple_relationships, valid_llm_result)
        # "PostgreSQL Database" is not in _GENERIC_CONTAINER_TYPES so stays
        assert simple_containers["db"]["container_type"] == "PostgreSQL Database"

    def test_notes_attached(self, simple_containers, simple_relationships, valid_llm_result):
        apply_enrichments(simple_containers, simple_relationships, valid_llm_result)
        assert "llm_notes" in simple_containers["api"]

    def test_confidence_stored(self, simple_containers, simple_relationships, valid_llm_result):
        apply_enrichments(simple_containers, simple_relationships, valid_llm_result)
        assert simple_containers["api"]["llm_confidence"] == pytest.approx(0.88)

    def test_na_protocol_updated(self, simple_containers, simple_relationships, valid_llm_result):
        # db has protocol "N/A"; LLM says "PostgreSQL"
        apply_enrichments(simple_containers, simple_relationships, valid_llm_result)
        assert simple_containers["db"]["protocol"] == "PostgreSQL"

    def test_http_protocol_not_replaced(self, simple_containers, simple_relationships):
        # api already has HTTP; even if LLM says HTTP too, it should be fine
        llm_result = {
            "containers": [{
                "name": "api", "verdict": "keep",
                "container_type": None, "technology": None,
                "protocol": "gRPC",  # LLM says gRPC but rule said HTTP
                "description": None, "confidence": 0.7, "notes": "",
            }],
            "inferred_relationships": [],
        }
        apply_enrichments(simple_containers, simple_relationships, llm_result)
        # HTTP should NOT be replaced by gRPC — HTTP != "N/A" or None
        assert simple_containers["api"]["protocol"] == "HTTP"


class TestApplyEnrichmentsDiscard:
    def test_discard_verdict_marked(self, simple_containers, simple_relationships):
        llm_result = {
            "containers": [{
                "name": "api", "verdict": "discard",
                "container_type": None, "technology": None, "protocol": None,
                "description": None, "confidence": 0.9, "notes": "Init container.",
            }],
            "inferred_relationships": [],
        }
        apply_enrichments(simple_containers, simple_relationships, llm_result)
        assert simple_containers["api"]["llm_verdict"] == "discard"

    def test_discarded_container_not_field_updated(self, simple_containers, simple_relationships):
        """Discarded containers should only get the verdict flag, not field updates."""
        original_type = simple_containers["api"]["container_type"]
        llm_result = {
            "containers": [{
                "name": "api", "verdict": "discard",
                "container_type": "CHANGED", "technology": "CHANGED",
                "protocol": None, "description": None, "confidence": 0.9, "notes": "",
            }],
            "inferred_relationships": [],
        }
        apply_enrichments(simple_containers, simple_relationships, llm_result)
        # container_type should NOT be updated on discard
        assert simple_containers["api"]["container_type"] == original_type


class TestApplyEnrichmentsMerge:
    def test_merge_verdict_marked(self, simple_containers, simple_relationships):
        llm_result = {
            "containers": [{
                "name": "api", "verdict": "merge", "merge_into": "gateway",
                "container_type": None, "technology": None, "protocol": None,
                "description": None, "confidence": 0.8, "notes": "",
            }],
            "inferred_relationships": [],
        }
        apply_enrichments(simple_containers, simple_relationships, llm_result)
        assert simple_containers["api"]["llm_verdict"] == "merge"
        assert simple_containers["api"]["llm_merge_into"] == "gateway"


class TestApplyEnrichmentsInferredRelationships:
    def test_inferred_rel_appended_to_container(self, simple_containers, simple_relationships, valid_llm_result):
        apply_enrichments(simple_containers, simple_relationships, valid_llm_result)
        rels = simple_containers["api"].get("relationships", [])
        llm_rels = [r for r in rels if r.get("source") == "llm"]
        assert len(llm_rels) == 1
        assert llm_rels[0]["to"] == "db"
        assert llm_rels[0]["port"] == "5432"

    def test_self_reference_inferred_rel_excluded(self, simple_containers, simple_relationships):
        llm_result = {
            "containers": [],
            "inferred_relationships": [{
                "from": "api", "to": "api",  # self-reference
                "type": "uses", "protocol": "HTTP", "confidence": 0.5,
            }],
        }
        apply_enrichments(simple_containers, simple_relationships, llm_result)
        llm_rels = [r for r in simple_containers["api"].get("relationships", [])
                    if r.get("source") == "llm"]
        assert llm_rels == []

    def test_inferred_rel_for_unknown_container_excluded(self, simple_containers, simple_relationships):
        llm_result = {
            "containers": [],
            "inferred_relationships": [{
                "from": "nonexistent", "to": "db",
                "type": "uses", "protocol": "HTTP", "confidence": 0.7,
            }],
        }
        apply_enrichments(simple_containers, simple_relationships, llm_result)
        # "nonexistent" not in containers, so no rel added to any container
        for c in simple_containers.values():
            llm_rels = [r for r in c.get("relationships", []) if r.get("source") == "llm"]
            assert llm_rels == []


# ---------------------------------------------------------------------------
# enrich_containers (integration, with mocked LLM)
# ---------------------------------------------------------------------------

class TestEnrichContainers:
    def test_no_llm_manager_returns_skipped(self, simple_containers, simple_relationships):
        stats = enrich_containers(simple_containers, simple_relationships, None)
        assert stats["skipped"] is True
        assert stats["enriched"] == 0

    def test_empty_containers_returns_skipped(self, simple_relationships):
        stats = enrich_containers({}, simple_relationships, MagicMock())
        assert stats["skipped"] is True

    def test_successful_enrichment(self, simple_containers, simple_relationships, valid_llm_result):
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = json.dumps(valid_llm_result)
        mock_llm.timeout = 30

        stats = enrich_containers(simple_containers, simple_relationships, mock_llm)

        assert stats["skipped"] is False
        assert stats["error"] is None
        assert stats["enriched"] >= 1

    def test_llm_returns_empty_string(self, simple_containers, simple_relationships):
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = ""
        mock_llm.timeout = 30

        stats = enrich_containers(simple_containers, simple_relationships, mock_llm)
        assert stats["error"] == "empty_response"

    def test_llm_returns_garbage(self, simple_containers, simple_relationships):
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = "I cannot help with that."
        mock_llm.timeout = 30

        stats = enrich_containers(simple_containers, simple_relationships, mock_llm)
        assert stats["error"] == "parse_failed"
        # Containers must be unchanged
        assert simple_containers["api"]["container_type"] == "Service"

    def test_llm_raises_exception(self, simple_containers, simple_relationships):
        mock_llm = MagicMock()
        mock_llm.generate_text.side_effect = OSError("connection refused")
        mock_llm.timeout = 30

        stats = enrich_containers(simple_containers, simple_relationships, mock_llm)
        assert stats["error"] is not None
        assert stats["skipped"] is False

    def test_timeout_restored_on_success(self, simple_containers, simple_relationships, valid_llm_result):
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = json.dumps(valid_llm_result)
        mock_llm.timeout = 30

        enrich_containers(simple_containers, simple_relationships, mock_llm)
        assert mock_llm.timeout == 30  # must be restored

    def test_timeout_restored_on_exception(self, simple_containers, simple_relationships):
        mock_llm = MagicMock()
        mock_llm.generate_text.side_effect = RuntimeError("boom")
        mock_llm.timeout = 30

        enrich_containers(simple_containers, simple_relationships, mock_llm)
        assert mock_llm.timeout == 30  # restored even after exception

    def test_batch_size_capped(self, simple_relationships):
        # Create 30 containers — only MAX_CONTAINERS_PER_BATCH (25) should be sent
        containers = {
            f"svc-{i}": {
                "name": f"svc-{i}",
                "container_type": "Service",
                "technology": "Unknown",
                "protocol": "HTTP",
                "path": f"services/svc-{i}",
                "deployment": None,
                "description": "",
                "dependencies_internal": [],
                "relationships": [],
            }
            for i in range(30)
        }

        sent_prompts = []

        def capture_prompt(prompt, **kwargs):
            sent_prompts.append(prompt)
            return json.dumps({"containers": [], "inferred_relationships": []})

        mock_llm = MagicMock()
        mock_llm.generate_text.side_effect = capture_prompt
        mock_llm.timeout = 30

        enrich_containers(containers, [], mock_llm)

        # The prompt should contain at most 25 container names, not all 30
        prompt = sent_prompts[0]
        # Count unique "svc-N" occurrences in the evidence section
        # (only 25 out of 30 should be in the bundle)
        contained = sum(1 for i in range(30) if f'"svc-{i}"' in prompt)
        assert contained <= 25

    def test_inferred_relationships_counted_in_stats(
        self, simple_containers, simple_relationships, valid_llm_result
    ):
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = json.dumps(valid_llm_result)
        mock_llm.timeout = 30

        stats = enrich_containers(simple_containers, simple_relationships, mock_llm)
        assert stats["inferred_relationships"] >= 1


# ---------------------------------------------------------------------------
# _should_update_field helper
# ---------------------------------------------------------------------------

class TestShouldUpdateField:
    def test_none_value_should_update(self):
        assert _should_update_field(None, _GENERIC_CONTAINER_TYPES) is True

    def test_generic_value_should_update(self):
        assert _should_update_field("Service", _GENERIC_CONTAINER_TYPES) is True
        assert _should_update_field("Unknown", _GENERIC_TECHNOLOGIES) is True

    def test_specific_value_should_not_update(self):
        assert _should_update_field("PostgreSQL Database", _GENERIC_CONTAINER_TYPES) is False
        assert _should_update_field("Python/FastAPI", _GENERIC_TECHNOLOGIES) is False
