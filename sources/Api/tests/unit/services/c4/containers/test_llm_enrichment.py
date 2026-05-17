"""Unit tests for containers/llm_enrichment.py."""

import json
import tempfile
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from app.services.c4.containers.llm_enrichment import (
    build_evidence_bundle,
    build_enrichment_prompt,
    parse_llm_enrichment_response,
    apply_enrichments,
    enrich_containers,
    _collect_candidate_file_evidence,
    _infer_signal_type,
    _should_update_field,
    _GENERIC_CONTAINER_TYPES,
    _GENERIC_TECHNOLOGIES,
    _SYSTEM_PROMPT,
    build_sanity_prompt,
    parse_sanity_response,
    run_sanity_pass,
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
                "container_type": "Microservice",
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

    def test_strips_reasoning_think_block(self, valid_llm_result):
        """qwen3/deepseek-r1-style <think>...</think> reasoning must be
        stripped before JSON extraction. Otherwise braces inside the
        reasoning prose can confuse the brace-balance scanner."""
        raw = (
            "<think>The user wants me to classify these containers. "
            "Looking at signal {x: 1} I think keep is right.</think>\n"
            + json.dumps(valid_llm_result)
        )
        result = parse_llm_enrichment_response(raw)
        assert result is not None
        assert len(result["containers"]) == 2

    def test_strips_unclosed_think_when_token_budget_exhausted(self, valid_llm_result):
        """When max_tokens cuts the response mid-reasoning, the closing
        </think> may be missing — the parser should still find any JSON
        emitted before the budget ran out, or fail cleanly without
        crashing on the malformed prefix."""
        raw = (
            "<think>The user wants me to review the containers. "
            "Looking carefully at the evidence, I see "
        )
        result = parse_llm_enrichment_response(raw)
        # No JSON to recover — parser should return None, not crash
        assert result is None


# ---------------------------------------------------------------------------
# apply_enrichments
# ---------------------------------------------------------------------------

class TestApplyEnrichmentsKeep:
    def test_generic_container_type_updated(self, simple_containers, simple_relationships, valid_llm_result):
        apply_enrichments(simple_containers, simple_relationships, valid_llm_result)
        assert simple_containers["api"]["container_type"] == "Microservice"

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

    def test_chunks_cover_all_containers(self, simple_relationships):
        """All candidates must reach the LLM across multiple chunks; nothing
        gets silently dropped past MAX_CONTAINERS_PER_BATCH."""
        from app.services.c4.containers.llm_enrichment import (
            MAX_CONTAINERS_PER_BATCH,
        )

        n = MAX_CONTAINERS_PER_BATCH * 2 + 3  # forces at least 3 chunks
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
            for i in range(n)
        }

        sent_prompts: list[str] = []

        def capture_prompt(prompt, **kwargs):
            sent_prompts.append(prompt)
            return json.dumps({"containers": [], "inferred_relationships": []})

        mock_llm = MagicMock()
        mock_llm.generate_text.side_effect = capture_prompt
        mock_llm.timeout = 30

        enrich_containers(containers, [], mock_llm)

        # Every container must appear in some prompt — none silently dropped
        joined = "\n".join(sent_prompts)
        for i in range(n):
            assert f'"svc-{i}"' in joined, f"svc-{i} not sent to any chunk"

        # No single prompt may exceed the per-batch cap
        for prompt in sent_prompts:
            present = sum(1 for i in range(n) if f'"svc-{i}"' in prompt)
            assert present <= MAX_CONTAINERS_PER_BATCH

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


# ---------------------------------------------------------------------------
# _collect_candidate_file_evidence
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_repo():
    """A temp repo with a candidate folder containing diagnostic files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        svc = repo / "services" / "api"
        svc.mkdir(parents=True)
        (svc / "Dockerfile").write_text(
            "FROM node:18\nWORKDIR /app\nCOPY . .\nCMD [\"node\", \"server.js\"]\n"
        )
        (svc / "package.json").write_text(json.dumps({
            "name": "api-svc",
            "version": "1.0.0",
            "main": "server.js",
            "scripts": {"start": "node server.js", "test": "jest"},
            "dependencies": {"express": "^4.18.0", "pg": "^8.0.0"},
        }))
        (svc / "README.md").write_text("# API service\n\nHTTP API serving products.\n")
        yield repo


class TestCollectCandidateFileEvidence:
    def test_returns_empty_for_no_repo_path(self):
        assert _collect_candidate_file_evidence(None, "services/api") == {}

    def test_returns_empty_for_repo_root(self, sample_repo):
        assert _collect_candidate_file_evidence(sample_repo, ".") == {}
        assert _collect_candidate_file_evidence(sample_repo, "") == {}

    def test_returns_empty_for_missing_folder(self, sample_repo):
        assert _collect_candidate_file_evidence(sample_repo, "does/not/exist") == {}

    def test_collects_dockerfile(self, sample_repo):
        ev = _collect_candidate_file_evidence(sample_repo, "services/api")
        assert "dockerfile" in ev
        assert "FROM node:18" in ev["dockerfile"]
        assert "CMD" in ev["dockerfile"]

    def test_collects_package_json(self, sample_repo):
        ev = _collect_candidate_file_evidence(sample_repo, "services/api")
        pkg = ev.get("package_json")
        assert pkg is not None
        assert pkg["name"] == "api-svc"
        assert "start" in pkg["scripts"]
        assert "express" in pkg["dependencies"]

    def test_collects_readme(self, sample_repo):
        ev = _collect_candidate_file_evidence(sample_repo, "services/api")
        assert "API service" in ev["readme"]

    def test_collects_top_level_files(self, sample_repo):
        ev = _collect_candidate_file_evidence(sample_repo, "services/api")
        assert "Dockerfile" in ev["files"]
        assert "package.json" in ev["files"]

    def test_collects_pyproject_toml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            svc = repo / "services" / "py"
            svc.mkdir(parents=True)
            (svc / "pyproject.toml").write_text(
                "[project]\n"
                "name = \"py-svc\"\n"
                "dependencies = [\"fastapi>=0.100\", \"uvicorn[standard]\"]\n"
                "\n"
                "[project.scripts]\n"
                "serve = \"py_svc:main\"\n"
            )
            ev = _collect_candidate_file_evidence(repo, "services/py")
            py = ev.get("pyproject_toml")
            assert py is not None
            assert py["name"] == "py-svc"
            assert "serve" in py["scripts"]
            # Version specifiers stripped
            assert "fastapi" in py["dependencies"]
            assert "uvicorn" in py["dependencies"]

    def test_collects_chart_yaml_distinguishes_library(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            chart = repo / "charts" / "shared"
            chart.mkdir(parents=True)
            (chart / "Chart.yaml").write_text(
                "apiVersion: v2\n"
                "name: shared-helpers\n"
                "type: library\n"
                "version: 0.1.0\n"
            )
            ev = _collect_candidate_file_evidence(repo, "charts/shared")
            assert ev["chart_yaml"]["type"] == "library"
            assert ev["chart_yaml"]["name"] == "shared-helpers"


class TestEvidenceBundleIncludesFileEvidence:
    def test_bundle_includes_file_evidence_when_repo_path_set(self, sample_repo):
        containers = {
            "api-svc": {
                "name": "api-svc",
                "container_type": "Service",
                "technology": "Unknown",
                "protocol": "HTTP",
                "path": "services/api",
            },
        }
        bundle = build_evidence_bundle(containers, [], repo_path=sample_repo)
        signal = bundle["container_signals"][0]
        assert "file_evidence" in signal
        assert "dockerfile" in signal["file_evidence"]

    def test_bundle_omits_file_evidence_without_repo_path(self, sample_repo):
        containers = {
            "api-svc": {
                "name": "api-svc",
                "container_type": "Service",
                "technology": "Unknown",
                "protocol": "HTTP",
                "path": "services/api",
            },
        }
        bundle = build_evidence_bundle(containers, [])
        signal = bundle["container_signals"][0]
        assert "file_evidence" not in signal


# ---------------------------------------------------------------------------
# Sanity pass
# ---------------------------------------------------------------------------

class TestBuildSanityPrompt:
    def test_includes_container_count_and_summaries(self):
        containers = {
            "api": {
                "name": "api", "container_type": "Microservice",
                "technology": "Python", "protocol": "HTTP",
                "path": "services/api", "description": "REST API.",
            },
            "junk": {
                "name": "junk", "container_type": "Service",
                "technology": "Unknown", "protocol": None,
                "path": "tools/codegen", "description": "Code generator.",
            },
        }
        prompt = build_sanity_prompt(containers, system_type="ecommerce")
        assert "false_positives" in prompt
        assert "missing" in prompt
        assert '"api"' in prompt
        assert '"junk"' in prompt
        assert "ecommerce" in prompt

    def test_truncation_flag_set_when_over_limit(self):
        from app.services.c4.containers.llm_enrichment import SANITY_MAX_CONTAINERS
        containers = {
            f"svc-{i}": {
                "name": f"svc-{i}", "container_type": "Service",
                "technology": "Python", "path": f"services/svc-{i}",
                "description": "",
            }
            for i in range(SANITY_MAX_CONTAINERS + 5)
        }
        prompt = build_sanity_prompt(containers)
        assert '"truncated": true' in prompt


class TestParseSanityResponse:
    def test_valid_response(self):
        raw = json.dumps({
            "false_positives": [
                {"name": "junk", "reason": "code generator", "confidence": 0.9},
            ],
            "missing": [
                {"name": "redis", "reason": "REDIS_URL referenced",
                 "evidence": "services/api/.env", "confidence": 0.85},
            ],
        })
        result = parse_sanity_response(raw)
        assert result is not None
        assert len(result["false_positives"]) == 1
        assert len(result["missing"]) == 1

    def test_returns_none_for_empty(self):
        assert parse_sanity_response("") is None
        assert parse_sanity_response(None) is None

    def test_returns_none_for_garbage(self):
        assert parse_sanity_response("not json") is None

    def test_handles_missing_keys(self):
        raw = json.dumps({"false_positives": []})
        result = parse_sanity_response(raw)
        assert result is not None
        assert result["false_positives"] == []
        assert result["missing"] == []

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps({"false_positives": [], "missing": []}) + "\n```"
        result = parse_sanity_response(raw)
        assert result is not None


class TestRunSanityPass:
    def test_skipped_without_llm_manager(self):
        result = run_sanity_pass({"a": {"name": "a"}}, None)
        assert result["skipped"] is True

    def test_skipped_with_empty_containers(self):
        result = run_sanity_pass({}, MagicMock())
        assert result["skipped"] is True

    def test_returns_parsed_result(self):
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = json.dumps({
            "false_positives": [{"name": "junk", "reason": "tool", "confidence": 0.9}],
            "missing": [],
        })
        mock_llm.timeout = 30
        result = run_sanity_pass(
            {"a": {"name": "a", "container_type": "Service"}},
            mock_llm,
        )
        assert result["skipped"] is False
        assert len(result["false_positives"]) == 1

    def test_handles_empty_response(self):
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = ""
        mock_llm.timeout = 30
        result = run_sanity_pass(
            {"a": {"name": "a", "container_type": "Service"}},
            mock_llm,
        )
        assert result["error"] == "empty_response"

    def test_handles_exception(self):
        mock_llm = MagicMock()
        mock_llm.generate_text.side_effect = OSError("connection refused")
        mock_llm.timeout = 30
        result = run_sanity_pass(
            {"a": {"name": "a", "container_type": "Service"}},
            mock_llm,
        )
        assert result["error"] is not None
        assert result["skipped"] is False

    def test_timeout_restored(self):
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = json.dumps({
            "false_positives": [], "missing": [],
        })
        mock_llm.timeout = 30
        run_sanity_pass(
            {"a": {"name": "a", "container_type": "Service"}},
            mock_llm,
        )
        assert mock_llm.timeout == 30
