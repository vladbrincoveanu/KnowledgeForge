"""LLM enrichment layer for C4 Level 2 container extraction.

Second-pass enrichment that runs **after** rule-based detectors
(Structure → Compose → Helm → Terraform → merge/dedup).

Pipeline:
    1. build_evidence_bundle()        – compress raw containers + relationships
                                        into typed evidence signals
    2. build_enrichment_prompt()      – system context + 2 few-shot examples
                                        + evidence bundle, single user message
    3. llm_manager.generate_text()   – one batched LLM call (never per-container)
    4. parse_llm_enrichment_response() – strip markdown, extract + validate JSON
    5. apply_enrichments()            – conservative merge back into containers dict;
                                        never overwrites confident rule-based data

Integration:
    Called from ContainerManager.enrich_containers_with_llm() which is invoked
    by C4ArchitectureExtractor._extract_level2_containers() after detect_all_containers().
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import yaml

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

from app.domain.review_queue import enqueue_review_item_if_low_confidence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

MAX_CONTAINERS_PER_BATCH = 12   # cap prompt size for small-context models
MAX_SIGNALS_PER_CONTAINER = 2   # drop extra signals from noisy containers
# Reasoning models (qwen3, deepseek-r1, etc.) burn output budget on
# <think>...</think> tokens before emitting JSON. 4096 leaves room for
# both reasoning AND the answer; non-reasoning models simply use less.
LLM_MAX_TOKENS = 4096
LLM_TEMPERATURE = 0.2           # low variance: we want factual classification
# A 9B-class reasoning model on a typical local GPU takes 3-8 minutes for a
# full 4K-token chunk: prompt processing + thinking + JSON. 600s gives
# headroom; smaller/non-reasoning models simply finish faster.
LLM_REQUEST_TIMEOUT_SEC = 600

# Sanity pass: minimum confidence required to act on a flagged false positive
SANITY_FALSE_POSITIVE_THRESHOLD = 0.7
# Bound the sanity prompt to a sensible upper limit; very large repos truncate.
SANITY_MAX_CONTAINERS = 80

# Field values the rule-based pipeline emits when it has no real signal —
# the LLM is allowed to overwrite these. Includes everything emitted by
# utils.infer_container_type so the LLM can correct misclassifications
# when file_evidence supports a more specific label (e.g. "Backend API",
# "Background Worker", "Code Generator", "Static Site Generator").
_GENERIC_CONTAINER_TYPES = frozenset({
    "Service", "Unknown", "Helm Deployed Service",
    "Containerized Service", "JavaScript Application",
    "Node.js Application", "Node.js Service",
    "Python Application", "Python Service",
    "Java Application", "Go Application", "Rust Application",
    "Frontend Application",
})
_GENERIC_TECHNOLOGIES = frozenset({"Unknown", "", None})
_GENERIC_DESCRIPTIONS = frozenset({
    "", "Kubernetes workload deployed via Helm.",
    "Kubernetes workload deployed via GitOps.",
    "Kubernetes workload deployed via Manifest.",
    "Kubernetes workload deployed via Kustomize.",
})

# ---------------------------------------------------------------------------
# System prompt — C4 container definition
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert software architect specialising in the C4 Model (Simon Brown).

C4 CONTAINER DEFINITION
A container is "an application or data store that needs to be running for the
system to work." Examples: web APIs, SPAs, mobile apps, databases, message buses,
file stores, background workers, caches.

NOT containers (discard these): one-off init/migration tasks (Flyway, Alembic),
CI scripts, build tools (webpack, gradle wrapper), test fixtures, mock servers
used only in dev. Infrastructure-as-Code repositories containing only Terraform,
Helm charts, or Kustomize overlays without application source code — these are
deployment descriptors, not running applications. However, workloads DEFINED
inside these repos (e.g., a StatefulSet deploying Kafka) ARE containers.

AMBIGUOUS CASES
  • Sidecar containers (envoy, istio-proxy): discard — infrastructure, not application
  • Multi-stage Dockerfile build stage: discard — not a runtime unit
  • "wait-for" helper images: discard — only ensures startup order

EVIDENCE
Each container_signal may include "file_evidence" with high-signal artifacts
read from the candidate folder:
  • dockerfile:     Dockerfile content (truncated). CMD/ENTRYPOINT presence is
                    strong evidence of a runtime unit.
  • package_json:   {name, version, main, type, scripts, dependencies}.
                    A "start" script + http framework dep ⇒ likely a service.
                    No "start" script ⇒ likely a library/tool.
  • pyproject_toml: {name, scripts, dependencies}. [project.scripts] entries
                    ⇒ runnable CLI/service. No scripts + no __main__.py in files
                    ⇒ likely a library, discard at L2.
  • chart_yaml:     {name, type, version, dependencies}. type=="library"
                    ⇒ Helm subchart, NOT a runtime container, discard.
  • readme:         First ~30 lines. Use to infer purpose; phrases like
                    "shared utilities", "test fixtures", "code generator",
                    "build tool" almost always mean discard at L2.
  • files:          Top-level entries in the candidate folder.

Use file_evidence aggressively. A folder with no Dockerfile, no start script,
no main entry point, and a README labelling it a library/tool is a discard.

YOUR TASK
Given a JSON evidence bundle produced by a static-analysis pipeline, return a
JSON object (no markdown, no comments) that:
  1. Reviews each detected container: verdict = keep | discard | merge
  2. Improves container_type, technology, protocol when the evidence is clear
  3. Infers additional relationships from env-var patterns, image names, ports
  4. Writes concise 1-2 sentence descriptions

OUTPUT SCHEMA (strict JSON, every container must appear, null = keep existing):
{
  "containers": [
    {
      "name":           "<original name>",
      "verdict":        "keep" | "discard" | "merge",
      "merge_into":     "<target name, only when verdict=merge, else omit>",
      "container_type": "<improved type  | null>",
      "technology":     "<improved stack | null>",
      "protocol":       "<improved proto | null>",
      "description":    "<1-2 sentences  | null>",
      "confidence":     0.0-1.0,
      "notes":          "<≤25-word reasoning>"
    }
  ],
  "inferred_relationships": [
    {
      "from":        "<container name>",
      "to":          "<container name>",
      "type":        "uses" | "publishes-to" | "subscribes-to" | "shares-volume",
      "protocol":    "<protocol>",
      "port":        "<port number or empty string>",
      "description": "<short label>",
      "confidence":  0.0-1.0
    }
  ]
}\
"""

# ---------------------------------------------------------------------------
# Few-shot examples — compact single example
# ---------------------------------------------------------------------------

_FEW_SHOT_EXAMPLES: list[dict[str, Any]] = [
    {
        "label": "Infrastructure-only repo (discard)",
        "input": {
            "repo_context": {
                "total_containers": 2,
                "detection_sources": ["helm", "terraform"],
                "is_infrastructure_only": True,
            },
            "container_signals": [
                {
                    "name": "ingress-nginx",
                    "signals": [{"signal_type": "infrastructure-only", "source_file": "helm/ingress-nginx/values.yaml", "attributes": {"deployment": "Helm"}, "confidence": 0.80}],
                },
                {
                    "name": "cert-manager",
                    "signals": [{"signal_type": "infrastructure-only", "source_file": "terraform/cert_manager.tf", "attributes": {"deployment": "Terraform"}, "confidence": 0.85}],
                },
            ],
            "relationship_signals": [],
        },
        "output": {
            "containers": [
                {
                    "name": "ingress-nginx", "verdict": "discard",
                    "container_type": None, "technology": None, "protocol": None,
                    "description": None, "confidence": 0.90,
                    "notes": "Ingress controller is infrastructure; no application source code in repo.",
                },
                {
                    "name": "cert-manager", "verdict": "discard",
                    "container_type": None, "technology": None, "protocol": None,
                    "description": None, "confidence": 0.88,
                    "notes": "Certificate management operator; infrastructure component, not an application container.",
                },
            ],
            "inferred_relationships": [],
        },
    },
    {
        "label": "Microservice + MongoDB",
        "input": {
            "repo_context": {"total_containers": 2, "detection_sources": ["compose"]},
            "container_signals": [
                {
                    "name": "ts-order-service",
                    "signals": [{"signal_type": "docker-compose-service", "source_file": "docker-compose.yml", "attributes": {"image": "codewisdom/ts-order-service:latest", "depends_on": ["ts-order-mongo"]}, "confidence": 0.9}],
                },
                {
                    "name": "ts-order-mongo",
                    "signals": [{"signal_type": "docker-compose-service", "source_file": "docker-compose.yml", "attributes": {"image": "mongo:latest"}, "confidence": 0.95}],
                },
            ],
            "relationship_signals": [{
                "from": "ts-order-service", "to": "ts-order-mongo",
                "type": "uses", "protocol": "MongoDB", "source": "compose", "confidence": 0.9,
            }],
        },
        "output": {
            "containers": [
                {
                    "name": "ts-order-service", "verdict": "keep",
                    "container_type": "Microservice", "technology": "Java/Spring Boot",
                    "protocol": "HTTP",
                    "description": "Manages train ticket order lifecycle and persists orders to MongoDB.",
                    "confidence": 0.85,
                    "notes": "Spring Boot microservice; env var MONGODB_HOST confirms DB dependency.",
                },
                {
                    "name": "ts-order-mongo", "verdict": "keep",
                    "container_type": "Database", "technology": "MongoDB",
                    "protocol": "MongoDB",
                    "description": "MongoDB datastore holding train ticket orders.",
                    "confidence": 0.95,
                    "notes": "Official mongo image on port 27017.",
                },
            ],
            "inferred_relationships": [{
                "from": "ts-order-service", "to": "ts-order-mongo",
                "type": "uses", "protocol": "MongoDB", "port": "27017",
                "description": "Order service reads/writes orders",
                "confidence": 0.92,
            }],
        },
    },
]


# ---------------------------------------------------------------------------
# Evidence bundle builder
# ---------------------------------------------------------------------------

def _infer_signal_type(container: dict[str, Any]) -> str:
    """Derive a signal_type label from a container dict's deployment metadata."""
    deployment = (container.get("deployment") or "").lower()
    path = (container.get("path") or "").lower()
    tech = (container.get("technology") or "").lower()

    if "terraform" in deployment:
        return "terraform-resource"
    if deployment == "helm":
        return "helm-chart"
    if deployment in ("kustomize", "manifest"):
        return "kustomize-manifest"
    if deployment == "gitops":
        return "helm-chart"
    if "values.yaml" in path:
        return "helm-values"
    if "/" in tech or (":" in tech and "kubernetes" not in tech):
        # looks like a docker image name (e.g. "postgres", "confluentinc/cp-kafka")
        return "docker-compose-service"
    return "filesystem-structure"


def _container_attributes(container: dict[str, Any]) -> dict[str, Any]:
    """Extract the most diagnostic attributes from a container dict."""
    attrs: dict[str, Any] = {}

    for field in ("container_type", "technology", "protocol",
                  "runtime_info", "runtime_environment", "deployment", "path"):
        val = container.get(field)
        if val and val not in ("Unknown", "N/A", ""):
            attrs[field] = val

    deps = container.get("dependencies_internal") or []
    if deps:
        attrs["depends_on"] = deps[:5]

    health = container.get("health_endpoint") or ""
    if health:
        attrs["health_endpoint"] = health

    return attrs


def _signal_confidence(signal_type: str) -> float:
    """Assign base confidence to a signal based on its type."""
    return {
        "terraform-resource": 0.95,
        "docker-compose-service": 0.90,
        "helm-chart": 0.85,
        "helm-values": 0.80,
        "kustomize-manifest": 0.80,
        "infrastructure-only": 0.65,
        "filesystem-structure": 0.60,
    }.get(signal_type, 0.70)


# ---------------------------------------------------------------------------
# File evidence collection — diagnostic file contents per candidate folder
# ---------------------------------------------------------------------------

# Sizes calibrated so a chunk of MAX_CONTAINERS_PER_BATCH candidates with full
# file evidence fits comfortably under typical model context windows.
_DOCKERFILE_MAX_CHARS = 1500
_README_MAX_LINES = 30
_README_MAX_CHARS = 1500
_FILES_LIST_MAX = 25
_PKG_DEPS_MAX = 20
_PKG_SCRIPTS_MAX = 10
_CHART_DEPS_MAX = 10


def _read_text_safely(path: Path, max_chars: int) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return None


def _collect_package_json(folder: Path) -> Optional[dict[str, Any]]:
    pkg = folder / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        "name": data.get("name"),
        "version": data.get("version"),
        "main": data.get("main"),
        "type": data.get("type"),
        "scripts": list((data.get("scripts") or {}).keys())[:_PKG_SCRIPTS_MAX],
        "dependencies": list((data.get("dependencies") or {}).keys())[:_PKG_DEPS_MAX],
    }


def _collect_pyproject_toml(folder: Path) -> Optional[dict[str, Any]]:
    if tomllib is None:
        return None
    pyproject = folder / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
    except (OSError, ValueError):
        return None
    project = data.get("project") if isinstance(data, dict) else None
    if not isinstance(project, dict):
        return None
    deps = project.get("dependencies") or []
    # Strip version/extras specifiers: "fastapi>=0.100" → "fastapi"
    dep_names: list[str] = []
    for dep in deps[:_PKG_DEPS_MAX]:
        if isinstance(dep, str):
            dep_names.append(re.split(r"[\s\[<>=!~;]", dep, 1)[0])
    return {
        "name": project.get("name"),
        "scripts": list((project.get("scripts") or {}).keys())[:_PKG_SCRIPTS_MAX],
        "dependencies": dep_names,
    }


def _collect_chart_yaml(folder: Path) -> Optional[dict[str, Any]]:
    chart = folder / "Chart.yaml"
    if not chart.is_file():
        return None
    try:
        data = yaml.safe_load(chart.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    deps_raw = data.get("dependencies") or []
    deps = [
        d.get("name") for d in deps_raw
        if isinstance(d, dict) and d.get("name")
    ][:_CHART_DEPS_MAX]
    return {
        "name": data.get("name"),
        "type": data.get("type"),  # "application" or "library"
        "version": data.get("version"),
        "dependencies": deps,
    }


def _collect_readme(folder: Path) -> Optional[str]:
    for candidate in ("README.md", "Readme.md", "readme.md", "README", "README.rst"):
        readme = folder / candidate
        if not readme.is_file():
            continue
        try:
            lines = readme.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return None
        return "\n".join(lines[:_README_MAX_LINES])[:_README_MAX_CHARS]
    return None


def _collect_candidate_file_evidence(
    repo_path: Optional[Path],
    container_path: Optional[str],
) -> dict[str, Any]:
    """Read small, high-signal files from a candidate folder.

    Best-effort: any read error returns whatever was gathered so far.
    Skipped for repo-root paths because their contents are too broad to
    be diagnostic of a single container — the file_evidence is meant to
    distinguish candidate folders, not summarise the whole repo.
    """
    if not repo_path or not container_path or container_path in {".", ""}:
        return {}

    folder = Path(repo_path) / container_path
    if not folder.is_dir():
        return {}

    evidence: dict[str, Any] = {}

    try:
        names = sorted(p.name for p in folder.iterdir())[:_FILES_LIST_MAX]
        evidence["files"] = names
    except OSError:
        return evidence

    dockerfile_text = _read_text_safely(folder / "Dockerfile", _DOCKERFILE_MAX_CHARS)
    if dockerfile_text is not None:
        evidence["dockerfile"] = dockerfile_text

    pkg_json = _collect_package_json(folder)
    if pkg_json:
        evidence["package_json"] = pkg_json

    pyproject = _collect_pyproject_toml(folder)
    if pyproject:
        evidence["pyproject_toml"] = pyproject

    chart = _collect_chart_yaml(folder)
    if chart:
        evidence["chart_yaml"] = chart

    readme = _collect_readme(folder)
    if readme:
        evidence["readme"] = readme

    return evidence


def build_evidence_bundle(
    containers: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    repo_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Compress rule-based detection output into a structured evidence bundle.

    Args:
        containers:    name → container dict (output of ContainerManager.detect_all_containers)
        relationships: list of relationship dicts (output of build_container_relationships)
        repo_path:     repo root, when provided each candidate gets a "file_evidence"
                       entry with diagnostic contents read from its folder

    Returns:
        Evidence bundle dict suitable for prompt serialisation.
    """
    detection_sources: set[str] = set()
    container_signals: list[dict[str, Any]] = []

    for name, container in containers.items():
        signal_type = _infer_signal_type(container)
        attrs = _container_attributes(container)
        conf = _signal_confidence(signal_type)

        # Track which detection phases contributed
        deployment = container.get("deployment", "")
        if deployment:
            detection_sources.add(deployment.lower())
        if signal_type == "docker-compose-service":
            detection_sources.add("compose")
        if signal_type == "filesystem-structure":
            detection_sources.add("structure")

        # Include any detector-level relationships as additional signals
        extra_signals: list[dict[str, Any]] = []
        for rel in (container.get("relationships") or [])[:MAX_SIGNALS_PER_CONTAINER]:
            extra_signals.append({
                "signal_type": "relationship",
                "source_file": rel.get("source", ""),
                "attributes": {
                    "to": rel.get("to"),
                    "type": rel.get("type"),
                    "protocol": rel.get("protocol"),
                },
                "confidence": 0.85,
            })

        signals: list[dict[str, Any]] = [{
            "signal_type": signal_type,
            "source_file": container.get("path", ""),
            "attributes": attrs,
            "confidence": conf,
        }]
        signals.extend(extra_signals[:MAX_SIGNALS_PER_CONTAINER - 1])

        signal_entry: dict[str, Any] = {
            "name": name,
            "existing": {
                "type": container.get("container_type"),
                "tech": container.get("technology"),
                "protocol": container.get("protocol"),
                "description": container.get("description") or "",
            },
            "signals": signals,
        }

        if repo_path is not None:
            file_evidence = _collect_candidate_file_evidence(
                repo_path, container.get("path"),
            )
            if file_evidence:
                signal_entry["file_evidence"] = file_evidence

        container_signals.append(signal_entry)

    def _rel_direction(rel_type: str) -> str:
        return "inbound" if rel_type == "subscribes-to" else "outbound"

    relationship_signals: list[dict[str, Any]] = [
        {
            "from": r.get("from", ""),
            "to": r.get("to", ""),
            "type": r.get("type", "uses"),
            "protocol": r.get("protocol", ""),
            "direction": _rel_direction(r.get("type", "uses")),
            "source": r.get("source", ""),
            "confidence": r.get("confidence", 0.85),
        }
        for r in relationships
        if r.get("from") and r.get("to")
    ]

    _app_sources = {"compose", "structure"}
    _infra_sources = {"helm", "terraform", "kustomize", "manifest", "gitops", "infrastructure-only"}
    is_infrastructure_only = bool(
        detection_sources
        and detection_sources.issubset(_infra_sources)
        and not detection_sources.intersection(_app_sources)
    )

    return {
        "repo_context": {
            "total_containers": len(containers),
            "detection_sources": sorted(detection_sources),
            "is_infrastructure_only": is_infrastructure_only,
        },
        "container_signals": container_signals,
        "relationship_signals": relationship_signals,
    }


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_enrichment_prompt(bundle: dict[str, Any]) -> str:
    """Assemble the complete LLM prompt: system context + few-shot + evidence."""
    sections: list[str] = []

    # System context (role + task)
    sections.append("=== SYSTEM CONTEXT ===")
    sections.append(_SYSTEM_PROMPT)

    # Few-shot examples
    sections.append("\n=== EXAMPLES ===")
    for i, ex in enumerate(_FEW_SHOT_EXAMPLES, 1):
        sections.append(f"\n--- Example {i}: {ex['label']} ---")
        sections.append("Input (evidence bundle):")
        sections.append(json.dumps(ex["input"], indent=2))
        sections.append("Expected output:")
        sections.append(json.dumps(ex["output"], indent=2))

    # Actual evidence
    sections.append("\n=== YOUR TASK ===")
    sections.append("Process the following evidence bundle and return ONLY a JSON object.")
    sections.append("Do NOT include markdown code fences, comments, or explanation.")
    sections.append("\nEvidence bundle:")
    sections.append(json.dumps(bundle, indent=2))

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# JSON extraction / response parser
# ---------------------------------------------------------------------------

_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.IGNORECASE | re.DOTALL)
_OPEN_THINK_TRAILING_RE = re.compile(r"<think\b[^>]*>.*\Z", re.IGNORECASE | re.DOTALL)


def _strip_reasoning_tags(text: str) -> str:
    """Remove <think>...</think> blocks emitted by reasoning models (qwen3,
    deepseek-r1, etc.). Also drops an unclosed trailing <think>... segment,
    which can occur when token budget is exhausted before the closing tag.
    """
    text = _THINK_BLOCK_RE.sub("", text)
    text = _OPEN_THINK_TRAILING_RE.sub("", text)
    return text


def _strip_markdown_fences(text: str) -> str:
    """Remove ``` or ```json fences from LLM output, and any reasoning tags."""
    text = _strip_reasoning_tags(text)
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _extract_json_object(text: str) -> Optional[str]:
    """Find the first top-level JSON object in text.

    Reasoning-model output (e.g. <think>...</think>) is stripped first so
    JSON-like braces inside chain-of-thought don't get returned by mistake.
    """
    text = _strip_reasoning_tags(text)
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                return text[start: i + 1]
    return None


def parse_llm_enrichment_response(
    response_text: Optional[str],
) -> Optional[dict[str, Any]]:
    """Extract and validate the JSON envelope from the LLM response.

    Returns None if parsing fails or the result doesn't match the expected
    schema (must have a 'containers' list).
    """
    if not response_text:
        return None

    try:
        cleaned = _strip_markdown_fences(response_text)
        raw_json = _extract_json_object(cleaned) or cleaned
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        # Try to recover by finding the first valid JSON substring
        raw_json = _extract_json_object(response_text)
        if not raw_json:
            logger.debug("LLM enrichment: no JSON object found in response")
            return None
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.debug("LLM enrichment: JSON parse failed: %s", exc)
            return None

    if not isinstance(data, dict):
        logger.debug("LLM enrichment: response is not a JSON object")
        return None

    if "containers" not in data or not isinstance(data.get("containers"), list):
        logger.debug("LLM enrichment: response missing 'containers' list")
        return None

    return data


# ---------------------------------------------------------------------------
# Enrichment applier
# ---------------------------------------------------------------------------

def _should_update_field(existing_value: Any, generic_values: frozenset) -> bool:
    """Return True when an existing field holds a generic/unknown value."""
    if existing_value is None:
        return True
    if isinstance(existing_value, str) and existing_value.strip() in generic_values:
        return True
    return False


def apply_enrichments(
    containers: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    llm_result: dict[str, Any],
) -> None:
    """Merge LLM enrichment results back into the containers dict in-place.

    Strategy:
    - verdict=keep:    update generic fields; never overwrite confident rule data
    - verdict=discard: add llm_verdict="discard" marker (caller decides removal)
    - verdict=merge:   add llm_verdict="merge", llm_merge_into=<name>
    - inferred_relationships: appended to owning container's "relationships" list
                              with source="llm"; deduplication happens in build_container_relationships()
    """
    verdicts_applied = 0
    descriptions_improved = 0
    relationships_inferred = 0

    # Index LLM container verdicts by name for O(1) lookup
    verdict_index: dict[str, dict[str, Any]] = {}
    for item in llm_result.get("containers", []):
        name = item.get("name")
        if name:
            verdict_index[name] = item

    for container_name, container in containers.items():
        verdict_item = verdict_index.get(container_name)
        if not verdict_item:
            continue

        verdict = verdict_item.get("verdict", "keep")
        confidence = float(verdict_item.get("confidence", 0.5))

        # Tag every enriched container regardless of verdict
        container["llm_enriched"] = True
        container["llm_confidence"] = confidence

        if verdict == "discard":
            container["llm_verdict"] = "discard"
            verdicts_applied += 1
            continue

        if verdict == "merge":
            container["llm_verdict"] = "merge"
            container["llm_merge_into"] = verdict_item.get("merge_into", "")
            verdicts_applied += 1
            continue

        # verdict == "keep" (default) — apply field improvements
        container["llm_verdict"] = "keep"
        verdicts_applied += 1

        # container_type: only update if existing is generic
        llm_type = verdict_item.get("container_type")
        if llm_type and _should_update_field(
            container.get("container_type"), _GENERIC_CONTAINER_TYPES
        ):
            container["container_type"] = llm_type

        # technology: only update if existing is unknown/empty
        llm_tech = verdict_item.get("technology")
        if llm_tech and _should_update_field(
            container.get("technology"), _GENERIC_TECHNOLOGIES
        ):
            container["technology"] = llm_tech

        # protocol: only update if existing is None or "N/A" (not HTTP — HTTP may be correct)
        llm_protocol = verdict_item.get("protocol")
        if llm_protocol and container.get("protocol") in (None, "", "N/A"):
            container["protocol"] = llm_protocol

        # description: update if missing or generic boilerplate
        llm_desc = verdict_item.get("description")
        if llm_desc and _should_update_field(
            container.get("description") or "", _GENERIC_DESCRIPTIONS
        ):
            container["description"] = llm_desc
            descriptions_improved += 1

        # attach reasoning notes
        notes = verdict_item.get("notes")
        if notes:
            container["llm_notes"] = notes

    # Inferred relationships
    inferred = llm_result.get("inferred_relationships") or []
    for rel in inferred:
        from_name = rel.get("from", "")
        to_name = rel.get("to", "")
        if not from_name or not to_name or from_name == to_name:
            continue
        if from_name not in containers:
            continue

        enriched_rel: dict[str, Any] = {
            "from": from_name,
            "to": to_name,
            "type": rel.get("type", "uses"),
            "protocol": rel.get("protocol", "HTTP"),
            "source": "llm",
            "confidence": float(rel.get("confidence", 0.7)),
        }
        if rel.get("port"):
            enriched_rel["port"] = rel["port"]
        if rel.get("description"):
            enriched_rel["description"] = rel["description"]

        containers[from_name].setdefault("relationships", []).append(enriched_rel)
        relationships_inferred += 1

    logger.info(
        "LLM enrichment applied: %d verdicts, %d descriptions improved, "
        "%d relationships inferred",
        verdicts_applied, descriptions_improved, relationships_inferred,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def enrich_containers(
    containers: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    llm_manager: Any,
    repo_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Run LLM enrichment over detected containers and relationships.

    This is a best-effort second pass: if the LLM is unavailable or returns
    garbage the containers dict is returned unmodified.

    Args:
        containers:   name → container dict (mutated in-place on success)
        relationships: list of relationship dicts from build_container_relationships()
        llm_manager:  LLMManager instance (or None to skip)
        repo_path:    when provided, each candidate's evidence bundle includes
                      file_evidence (Dockerfile, package.json, README, etc.)
                      read from its folder

    Returns:
        Stats dict: {"enriched": int, "discarded": int, "inferred_relationships": int,
                     "skipped": bool, "error": str|None}
    """
    if llm_manager is None:
        logger.debug("LLM enrichment skipped: no llm_manager provided")
        return {"enriched": 0, "discarded": 0, "inferred_relationships": 0,
                "skipped": True, "error": None}

    if not containers:
        return {"enriched": 0, "discarded": 0, "inferred_relationships": 0,
                "skipped": True, "error": None}

    # Prioritise containers with generic types (most in need of enrichment).
    # Order matters across chunks: noisier candidates get classified first so
    # if a downstream batch fails the most-uncertain ones still got a verdict.
    def _enrichment_priority(item: tuple[str, dict]) -> int:
        name, c = item
        score = 0
        if c.get("container_type") in _GENERIC_CONTAINER_TYPES:
            score += 2
        if c.get("technology") in _GENERIC_TECHNOLOGIES:
            score += 1
        if not c.get("description"):
            score += 1
        return -score  # higher score → lower sort key → first in list

    ordered = sorted(containers.items(), key=_enrichment_priority)
    chunks: list[dict[str, dict[str, Any]]] = [
        dict(ordered[i:i + MAX_CONTAINERS_PER_BATCH])
        for i in range(0, len(ordered), MAX_CONTAINERS_PER_BATCH)
    ]

    logger.info(
        "LLM enrichment: %d containers split into %d chunk(s) of up to %d",
        len(containers), len(chunks), MAX_CONTAINERS_PER_BATCH,
    )

    aggregated: dict[str, Any] = {"containers": [], "inferred_relationships": []}
    chunk_errors: list[str] = []

    original_timeout = getattr(llm_manager, "timeout", 30)
    try:
        llm_manager.timeout = max(original_timeout, LLM_REQUEST_TIMEOUT_SEC)
        for idx, batch in enumerate(chunks, start=1):
            batch_rels = [r for r in relationships
                          if r.get("from") in batch or r.get("to") in batch]
            bundle = build_evidence_bundle(batch, batch_rels, repo_path=repo_path)
            prompt = build_enrichment_prompt(bundle)

            logger.info(
                "LLM enrichment chunk %d/%d: %d containers (%d relationships)",
                idx, len(chunks), len(batch), len(batch_rels),
            )

            try:
                raw_response = llm_manager.generate_text(
                    prompt,
                    max_tokens=LLM_MAX_TOKENS,
                    temperature=LLM_TEMPERATURE,
                    use_cache=True,
                )
            except Exception as exc:
                logger.warning("LLM enrichment chunk %d failed: %s", idx, exc)
                chunk_errors.append(f"chunk{idx}:{exc}")
                continue

            if not raw_response:
                logger.warning("LLM enrichment chunk %d: empty response", idx)
                chunk_errors.append(f"chunk{idx}:empty_response")
                continue

            parsed = parse_llm_enrichment_response(raw_response)
            if not parsed:
                logger.warning(
                    "LLM enrichment chunk %d: parse failed (first 300 chars): %s",
                    idx, raw_response[:300],
                )
                chunk_errors.append(f"chunk{idx}:parse_failed")
                continue

            aggregated["containers"].extend(parsed.get("containers", []) or [])
            aggregated["inferred_relationships"].extend(
                parsed.get("inferred_relationships", []) or []
            )
    finally:
        llm_manager.timeout = original_timeout

    if not aggregated["containers"] and not aggregated["inferred_relationships"]:
        # All chunks failed — surface the first error code for caller visibility
        first_error = chunk_errors[0].split(":", 1)[1] if chunk_errors else "no_results"
        return {"enriched": 0, "discarded": 0, "inferred_relationships": 0,
                "skipped": False, "error": first_error}

    # Apply aggregated enrichments to the full containers dict
    apply_enrichments(containers, relationships, aggregated)

    run_id = str(uuid4())
    for container in containers.values():
        llm_confidence = container.get("llm_confidence", 1.0)
        if llm_confidence < 0.70:
            enqueue_review_item_if_low_confidence(
                extraction_run_id=run_id,
                field="container_verdict",
                candidate_values=[container.get("container_type", "Unknown")],
                llm_suggestion=container.get("llm_notes"),
                confidence=llm_confidence,
                evidence=[
                    {
                        "container_name": container.get("name", ""),
                        "container_type": container.get("container_type"),
                        "technology": container.get("technology"),
                        "verdict": container.get("llm_verdict"),
                        "notes": container.get("llm_notes"),
                    }
                ],
            )

    enriched = sum(1 for c in containers.values() if c.get("llm_enriched"))
    discarded = sum(1 for c in containers.values() if c.get("llm_verdict") == "discard")
    inferred = sum(
        1 for c in containers.values()
        for r in c.get("relationships", [])
        if r.get("source") == "llm"
    )

    logger.info(
        "LLM enrichment complete: %d enriched, %d marked discard, %d relationships inferred",
        enriched, discarded, inferred,
    )
    return {
        "enriched": enriched,
        "discarded": discarded,
        "inferred_relationships": inferred,
        "skipped": False,
        "error": "; ".join(chunk_errors) if chunk_errors else None,
    }


# ===========================================================================
# Sanity pass — global completeness/correctness review over the surviving set
# ===========================================================================

_SANITY_SYSTEM_PROMPT = """\
You are reviewing the FINAL container list extracted from a code repository
at the C4 Model (Simon Brown) Level 2 (containers) abstraction.

C4 CONTAINER DEFINITION
A container is "an application or data store that needs to be running for
the system to work." Examples: web APIs, SPAs, mobile apps, databases,
message buses, file stores, background workers, caches.

NOT containers (do not keep them): build tools, code generators, shared
libraries, test fixtures, init/migration scripts, documentation sites
unless they are deployed and served.

YOUR TASK
Review the list of {n} containers below. Flag two things:
  1. false_positives — items that survived classification but DO NOT meet
     the C4 container definition. The per-candidate pass missed something.
  2. missing — containers that the system clearly needs (referenced in
     env vars, code imports, IaC, deployment configs) but which are NOT
     in the list.

Return ONLY a JSON object, no markdown, no commentary:
{{
  "false_positives": [
    {{"name": "<container name from input>",
      "reason": "<≤25 words>",
      "confidence": 0.0-1.0}}
  ],
  "missing": [
    {{"name": "<inferred name>",
      "reason": "<≤25 words>",
      "evidence": "<short pointer (file/path/import)>",
      "confidence": 0.0-1.0}}
  ]
}}

Be conservative. Only flag items you are confident about (>=0.7).
If everything looks correct, return both lists empty.\
"""


def _summarise_for_sanity(container: dict[str, Any]) -> dict[str, Any]:
    """Compact per-container view for the sanity pass — no file evidence."""
    return {
        "name": container.get("name"),
        "type": container.get("container_type"),
        "technology": container.get("technology"),
        "protocol": container.get("protocol"),
        "path": container.get("path"),
        "description": (container.get("description") or "")[:200],
    }


def build_sanity_prompt(
    containers: dict[str, dict[str, Any]],
    system_type: Optional[str] = None,
) -> str:
    """Build the sanity-pass prompt over the surviving container set."""
    summaries = [
        _summarise_for_sanity(c) for c in list(containers.values())[:SANITY_MAX_CONTAINERS]
    ]
    body = {
        "system_type": system_type or "unknown",
        "container_count": len(containers),
        "truncated": len(containers) > SANITY_MAX_CONTAINERS,
        "containers": summaries,
    }
    parts = [
        "=== SYSTEM CONTEXT ===",
        _SANITY_SYSTEM_PROMPT.format(n=len(containers)),
        "\n=== INPUT ===",
        json.dumps(body, indent=2),
        "\nReturn the JSON object now.",
    ]
    return "\n".join(parts)


def parse_sanity_response(response_text: Optional[str]) -> Optional[dict[str, Any]]:
    """Parse the sanity-pass response. Returns None on failure."""
    if not response_text:
        return None
    try:
        cleaned = _strip_markdown_fences(response_text)
        raw_json = _extract_json_object(cleaned) or cleaned
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        raw_json = _extract_json_object(response_text)
        if not raw_json:
            return None
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return None

    if not isinstance(data, dict):
        return None

    fps = data.get("false_positives")
    missing = data.get("missing")
    if not isinstance(fps, list):
        fps = []
    if not isinstance(missing, list):
        missing = []
    return {"false_positives": fps, "missing": missing}


def run_sanity_pass(
    containers: dict[str, dict[str, Any]],
    llm_manager: Any,
    system_type: Optional[str] = None,
) -> dict[str, Any]:
    """Run a single global review LLM call and return the parsed result.

    Returns:
        {"false_positives": [...], "missing": [...], "skipped": bool, "error": str|None}
    """
    if llm_manager is None or not containers:
        return {"false_positives": [], "missing": [], "skipped": True, "error": None}

    prompt = build_sanity_prompt(containers, system_type=system_type)
    logger.info("LLM sanity pass: reviewing %d containers", len(containers))

    original_timeout = getattr(llm_manager, "timeout", 30)
    try:
        llm_manager.timeout = max(original_timeout, LLM_REQUEST_TIMEOUT_SEC)
        try:
            raw = llm_manager.generate_text(
                prompt,
                max_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
                use_cache=True,
            )
        except Exception as exc:
            logger.warning("LLM sanity pass call failed: %s", exc)
            return {"false_positives": [], "missing": [], "skipped": False, "error": str(exc)}
    finally:
        llm_manager.timeout = original_timeout

    if not raw:
        return {"false_positives": [], "missing": [], "skipped": False, "error": "empty_response"}

    parsed = parse_sanity_response(raw)
    if parsed is None:
        logger.warning(
            "LLM sanity pass: could not parse response (first 300 chars): %s",
            raw[:300],
        )
        return {"false_positives": [], "missing": [], "skipped": False, "error": "parse_failed"}

    return {**parsed, "skipped": False, "error": None}
