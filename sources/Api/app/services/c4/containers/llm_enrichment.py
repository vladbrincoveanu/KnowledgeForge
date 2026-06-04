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

from app.domain.review_queue import enqueue_review_item_if_low_confidence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

MAX_CONTAINERS_PER_BATCH = 12   # cap prompt size for small-context models
MAX_SIGNALS_PER_CONTAINER = 2   # drop extra signals from noisy containers
LLM_MAX_TOKENS = 2048           # thinking models consume tokens on reasoning first
LLM_TEMPERATURE = 0.2           # low variance: we want factual classification

# Field values the rule-based pipeline emits when it has no real signal —
# the LLM is allowed to overwrite these.
_GENERIC_CONTAINER_TYPES = frozenset({
    "Service", "Unknown", "Helm Deployed Service",
    "Containerized Service", "JavaScript Application",
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
  • Paths under development/ directories: pipeline definitions, dev scripts, local
    tooling — discard unless there is a Dockerfile, docker-compose entry, or k8s
    manifest that proves this path runs as a deployed service

DISCARD CONSERVATISM RULE (applies to filesystem-structure and llm-proposed signals)
  Do NOT discard a container merely because:
    • technology = "Unknown" — infer the tech from the name, README excerpt, or file
      extension evidence and set verdict=keep with your best estimate.
    • No Dockerfile or deploy manifest was found — libraries, SDKs, and internal
      tooling packages without Dockerfiles are still C4 containers if they are
      independently versioned units that must exist for the system to work.
  Only discard a filesystem-structure container when you are confident (≥ 0.85)
  that the directory is a CI pipeline script folder, one-off migration script, or
  a build-time-only artifact with no runtime presence whatsoever.
  When in doubt between discard and keep, choose keep and note the ambiguity.

YOUR TASK
Given a JSON evidence bundle produced by a static-analysis pipeline, return a
JSON object (no markdown, no comments) that:
  1. Reviews each detected container: verdict = keep | discard | merge
  2. Improves container_type, technology, protocol when the evidence is clear
  3. Infers relationships between containers — see strategy below
  4. Writes concise 1-2 sentence descriptions

RELATIONSHIP INFERENCE STRATEGY (apply in order, stop when confident)
  Priority 1 — explicit signals (confidence 0.85-0.95):
    env_var_names containing another container's name (e.g. ROUTE_MANAGER_URL → calls route-manager)
    depends_on lists in docker-compose
    ports that expose well-known database/broker ports (5432, 6379, 9092, 5672)

  Priority 2 — readme/description text (confidence 0.70-0.84):
    README excerpt mentions another container name or role
    Description says "calls", "connects to", "publishes to", "subscribes from"

  If evidence is completely absent for a relationship, emit nothing — do not guess from names.

CONTAINER DETECTION SOURCES
Some containers have signal_type "llm-proposed": they were discovered in Phase 0 by
reading executable signals — docker-compose files, .env.example connection strings,
CI workflow files, and shell scripts with docker run/compose commands.
  • Keep them if their type and role make sense for this system (e.g. postgres when
    DATABASE_URL appears in .env.example, temporal when a workflow CI job references it).
  • Discard them only when confident they are NOT real runtime components.
  • Do NOT discard them merely because they have no filesystem-structure signal —
    external services like databases rarely have source code in the repo.\


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
        "label": "Thin-signal services with source cross-reference",
        "input": {
            "repo_context": {
                "total_containers": 2,
                "detection_sources": ["structure"],
                "is_infrastructure_only": False,
            },
            "container_signals": [
                {
                    "name": "order-service",
                    "existing": {"type": "ServerSideWebApp", "tech": "Python", "protocol": "HTTP", "description": ""},
                    "signals": [
                        {"signal_type": "filesystem-structure", "source_file": "services/order-service", "attributes": {"technology": "Python + FastAPI", "path": "services/order-service"}, "confidence": 0.60},
                        {"signal_type": "readme-excerpt", "source_file": "services/order-service/README", "attributes": {"description": "Manages order lifecycle. Sends confirmation emails via the notification-worker."}, "confidence": 0.70},
                    ],
                },
                {
                    "name": "notification-worker",
                    "existing": {"type": "Unknown", "tech": "Node.js", "protocol": "", "description": ""},
                    "signals": [
                        {"signal_type": "filesystem-structure", "source_file": "services/notification-worker", "attributes": {"technology": "Node.js", "path": "services/notification-worker"}, "confidence": 0.60},
                    ],
                },
            ],
            "relationship_signals": [
                {
                    "from": "order-service", "to": "notification-worker",
                    "type": "uses", "protocol": "", "direction": "outbound",
                    "source": "source-xref:src/clients.py (3 occurrences)", "confidence": 0.65,
                },
            ],
        },
        "output": {
            "containers": [
                {
                    "name": "order-service", "verdict": "keep",
                    "container_type": "ServerSideWebApp", "technology": "Python + FastAPI",
                    "protocol": "HTTP",
                    "description": "Manages the full order lifecycle and delegates email confirmations to notification-worker.",
                    "confidence": 0.80,
                    "notes": "README and source cross-reference confirm dependency on notification-worker.",
                },
                {
                    "name": "notification-worker", "verdict": "keep",
                    "container_type": "ServerSideConsoleApp", "technology": "Node.js",
                    "protocol": None,
                    "description": "Background worker that sends transactional emails on behalf of order-service.",
                    "confidence": 0.72,
                    "notes": "Referenced 3 times in order-service source; README confirms email role.",
                },
            ],
            "inferred_relationships": [
                {
                    "from": "order-service", "to": "notification-worker",
                    "type": "uses", "protocol": "HTTP", "port": "",
                    "description": "delegates email delivery to",
                    "confidence": 0.72,
                },
            ],
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
    if container.get("detection_source") == "llm-proposed":
        return "llm-proposed"

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


def _read_readme_excerpt(container_dir: Path, max_chars: int = 280) -> Optional[str]:
    """Return a short description excerpt from README, skipping title lines."""
    for name in ("README.md", "README.rst", "README.txt", "README"):
        readme = container_dir / name
        if not readme.is_file():
            continue
        try:
            text = readme.read_text(encoding="utf-8", errors="ignore")
            lines = [l.strip() for l in text.splitlines()
                     if l.strip() and not l.startswith("#") and not l.startswith("=")]
            excerpt = " ".join(lines[:6])
            return excerpt[:max_chars] if excerpt else None
        except OSError:
            pass
    return None


_SOURCE_EXTENSIONS = {
    ".py", ".go", ".ts", ".js", ".java", ".cs", ".rb", ".rs",
    ".sh", ".yaml", ".yml", ".env", ".toml", ".cfg", ".ini", ".json",
}
_SKIP_DIRS = {".git", "vendor", "node_modules", ".venv", "__pycache__", "dist", "build"}


def _scan_cross_service_refs(
    container_dir: Path,
    other_names: list[str],
    max_files: int = 30,
    max_bytes: int = 50_000,
) -> list[dict[str, Any]]:
    """Scan source files in *container_dir* for call-site references to other containers.

    A reference counts only when the container name appears in a meaningful call context:
      - URL/hostname:  ://name, http(s)://name, name:PORT, name/v1, name.svc
      - Env variable:  UPPER_CASE variant of the name (e.g. COMPUTE_API_URL)
      - Import/client: 'import name', 'from name', name appearing in a quoted string
                       alongside 'url', 'host', 'endpoint', 'client', 'base'

    Generic string occurrences (e.g. label values, comments) only count toward
    confidence when at least one of the above strong signals is also present.
    """
    if not container_dir.is_dir() or not other_names:
        return []

    # Build lookup: normalised variant → original name
    name_variants: dict[str, str] = {}
    for n in other_names:
        name_variants[n] = n
        alt = n.replace("-", "_") if "-" in n else n.replace("_", "-")
        if alt != n:
            name_variants[alt] = n

    results: dict[str, dict[str, Any]] = {}
    files_scanned = 0

    for path in container_dir.rglob("*"):
        if files_scanned >= max_files:
            break
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix not in _SOURCE_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:max_bytes]
        except OSError:
            continue
        files_scanned += 1

        for variant, original in name_variants.items():
            if variant not in text:
                continue

            # Strong signal 1: URL / hostname context
            url_pat = re.compile(
                r'(?:://|https?://)[^\s]*' + re.escape(variant) +
                r'|' + re.escape(variant) + r'(?::\d{2,5}|/v\d|\.svc|\.cluster)',
                re.IGNORECASE,
            )
            url_hits = len(url_pat.findall(text))

            # Strong signal 2: env-var naming (COMPUTE_API_URL, ROUTE_MANAGER_HOST …)
            env_base = variant.upper().replace("-", "_")
            env_pat = re.compile(r'\b' + re.escape(env_base) + r'[_A-Z]*\b')
            env_hits = len(env_pat.findall(text))

            # Strong signal 3: import / client context in quoted strings
            client_pat = re.compile(
                r'(?:import|from|client|url|host|endpoint|base)[^\n]{0,60}' +
                re.escape(variant),
                re.IGNORECASE,
            )
            client_hits = len(client_pat.findall(text))

            strong = url_hits + env_hits + client_hits
            generic_count = text.count(variant)

            # Require either a strong signal OR enough comment/label occurrences to
            # be worth passing to the LLM.  K8s label-based coordination (e.g.
            # route-manager watching a label set by hpc-gateway) shows up only in
            # comments but is still a real architectural coupling.
            if strong == 0 and generic_count < 3:
                continue

            if strong > 0:
                weighted = url_hits * 3 + env_hits * 2 + client_hits * 2 + min(generic_count, 10)
                confidence = min(0.80, 0.45 + weighted * 0.04)
            else:
                # Comment/label-only reference — low confidence, let the LLM decide
                confidence = min(0.35, 0.20 + generic_count * 0.03)

            existing = results.get(original)
            if existing is None or confidence > existing["confidence"]:
                results[original] = {
                    "referenced_name": original,
                    "file": str(path.relative_to(container_dir)),
                    "occurrences": generic_count,
                    "url_hits": url_hits,
                    "env_hits": env_hits,
                    "client_hits": client_hits,
                    "confidence": confidence,
                    "weak_only": strong == 0,
                }

    return list(results.values())


def _container_attributes(container: dict[str, Any]) -> dict[str, Any]:
    """Extract the most diagnostic attributes from a container dict."""
    attrs: dict[str, Any] = {}

    for field in ("container_type", "technology", "protocol", "image",
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

    ports = container.get("ports") or []
    if ports:
        attrs["ports"] = ports[:5]

    env_var_names = container.get("env_var_names") or []
    if env_var_names:
        attrs["env_var_names"] = env_var_names[:12]

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
        "llm-proposed": 0.55,
    }.get(signal_type, 0.70)


def build_evidence_bundle(
    containers: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    repo_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Compress rule-based detection output into a structured evidence bundle.

    Args:
        containers:    name → container dict (output of ContainerManager.detect_all_containers)
        relationships: list of relationship dicts (output of build_container_relationships)
        repo_path:     optional repo root Path; when provided, README excerpts are read
                       from each container's directory to supplement thin signals.

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

        primary_signal: dict[str, Any] = {
            "signal_type": signal_type,
            "source_file": container.get("path", "") or container.get("llm_discovery_signal", ""),
            "attributes": attrs,
            "confidence": conf,
        }
        # For llm-proposed containers, surface the original discovery signal
        if signal_type == "llm-proposed":
            primary_signal["attributes"]["discovery_signal"] = container.get("llm_discovery_signal", "")
            primary_signal["attributes"]["discovery_confidence"] = container.get("llm_discovery_confidence", 0.5)

        signals: list[dict[str, Any]] = [primary_signal]
        signals.extend(extra_signals[:MAX_SIGNALS_PER_CONTAINER - 1])

        # Flag containers inside development/ — likely dev tooling, not deployable
        container_path_str = container.get("path") or ""
        if any(part.lower() in {"development", "dev"} for part in Path(container_path_str).parts):
            signals.append({
                "signal_type": "dev-directory",
                "source_file": container_path_str,
                "attributes": {
                    "note": "Path is under a development/ directory. "
                            "Discard unless explicit deployment evidence exists."
                },
                "confidence": 0.85,
            })

        # README excerpt — adds purpose/context when structural signals are thin
        container_path_str = container.get("path") or ""
        container_dir: Optional[Path] = None
        if repo_path and container_path_str and container_path_str not in {".", ""}:
            container_dir = repo_path / container_path_str
            if container_dir.is_dir():
                excerpt = _read_readme_excerpt(container_dir)
                if excerpt:
                    signals.append({
                        "signal_type": "readme-excerpt",
                        "source_file": f"{container_path_str}/README",
                        "attributes": {"description": excerpt},
                        "confidence": 0.70,
                    })

        container_signals.append({
            "name": name,
            "existing": {
                "type": container.get("container_type"),
                "tech": container.get("technology"),
                "protocol": container.get("protocol"),
                "description": container.get("description") or "",
            },
            "signals": signals,
        })

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

    # Cross-reference scan: find containers whose names appear in other containers'
    # source files.  This gives the LLM real code evidence — not naming guesswork.
    if repo_path:
        all_names = list(containers.keys())
        for name, container in containers.items():
            c_path_str = container.get("path") or ""
            if not c_path_str or c_path_str in {".", ""}:
                continue
            c_dir = repo_path / c_path_str
            other_names = [n for n in all_names if n != name]
            hits = _scan_cross_service_refs(c_dir, other_names)
            for hit in hits:
                detail = (
                    f"url:{hit.get('url_hits',0)} "
                    f"env:{hit.get('env_hits',0)} "
                    f"client:{hit.get('client_hits',0)} "
                    f"generic:{hit['occurrences']}"
                )
                sig: dict[str, Any] = {
                    "from": name,
                    "to": hit["referenced_name"],
                    "type": "uses",
                    "protocol": "",
                    "direction": "outbound",
                    "source": f"source-xref:{hit['file']} ({detail})",
                    "confidence": hit["confidence"],
                }
                if hit.get("weak_only"):
                    sig["note"] = "comment/label-only reference — no direct API call detected; include only if the coupling is architecturally significant"
                relationship_signals.append(sig)
                logger.debug(
                    "Cross-ref: %s references %s in %s (%d times)",
                    name, hit["referenced_name"], hit["file"], hit["occurrences"],
                )

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
    sections.append(
        "Process the following evidence bundle.\n"
        "/no_think\n"
        "CRITICAL: Your entire response must be a single JSON object — nothing else.\n"
        "Start your response with { and end with }.\n"
        "Do NOT include markdown fences, reasoning text, or any explanation."
    )
    sections.append("\nEvidence bundle:")
    sections.append(json.dumps(bundle, indent=2))

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# JSON extraction / response parser
# ---------------------------------------------------------------------------

def _strip_thinking_tags(text: str) -> str:
    """Remove <think>...</think> blocks emitted by reasoning models (e.g. Qwen3)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _strip_markdown_fences(text: str) -> str:
    """Remove ``` or ```json fences from LLM output."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _extract_json_object(text: str, last: bool = False) -> Optional[str]:
    """Find a top-level JSON object in text.

    Args:
        text: Input string.
        last: If True, return the *last* top-level JSON object instead of the first.
              Useful when models emit reasoning text before the actual JSON output.
    """
    candidates: list[str] = []
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
                candidates.append(text[start: i + 1])
                start = None
    if not candidates:
        return None
    return candidates[-1] if last else candidates[0]


def _try_parse_json(text: str) -> Optional[dict[str, Any]]:
    """Attempt to parse text as a JSON object with 'containers' key."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if "containers" not in data or not isinstance(data.get("containers"), list):
        return None
    return data


def parse_llm_enrichment_response(
    response_text: Optional[str],
) -> Optional[dict[str, Any]]:
    """Extract and validate the JSON envelope from the LLM response.

    Tries multiple extraction strategies to handle models that emit reasoning
    text before or around the JSON output.

    Returns None if parsing fails or the result doesn't match the expected
    schema (must have a 'containers' list).
    """
    if not response_text:
        return None

    # Strip reasoning blocks first so they don't interfere with JSON extraction
    cleaned = _strip_thinking_tags(response_text)
    cleaned = _strip_markdown_fences(cleaned)

    # Strategy 1: the whole cleaned text is valid JSON
    result = _try_parse_json(cleaned)
    if result:
        return result

    # Strategy 2: last top-level JSON object (after reasoning preamble)
    last_json = _extract_json_object(cleaned, last=True)
    if last_json:
        result = _try_parse_json(last_json)
        if result:
            return result

    # Strategy 3: first top-level JSON object
    first_json = _extract_json_object(cleaned, last=False)
    if first_json and first_json != last_json:
        result = _try_parse_json(first_json)
        if result:
            return result

    # Strategy 4: raw response as fallback (model may not have stripped fences)
    last_raw = _extract_json_object(response_text, last=True)
    if last_raw:
        result = _try_parse_json(last_raw)
        if result:
            return result

    logger.debug(
        "LLM enrichment: could not parse valid response (first 300 chars): %s",
        response_text[:300],
    )
    return None


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

        # description: update if missing, generic boilerplate, or LLM is confident
        # enough to override non-architectural content scraped from README/docs.
        llm_desc = verdict_item.get("description")
        existing_desc = container.get("description") or ""
        if llm_desc and (
            _should_update_field(existing_desc, _GENERIC_DESCRIPTIONS)
            or confidence >= 0.75
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
        containers:    name → container dict (mutated in-place on success)
        relationships: list of relationship dicts from build_container_relationships()
        llm_manager:   LLMManager instance (or None to skip)
        repo_path:     optional repo root Path; enables README-based evidence signals

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

    # Batch: cap at MAX_CONTAINERS_PER_BATCH to stay within token budget
    # Prioritise containers with generic types (most in need of enrichment)
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
    batch = dict(ordered[:MAX_CONTAINERS_PER_BATCH])

    # Trim relationships to only those in the batch
    batch_rels = [r for r in relationships
                  if r.get("from") in batch or r.get("to") in batch]

    # Build evidence bundle and prompt
    bundle = build_evidence_bundle(batch, batch_rels, repo_path=repo_path)
    prompt = build_enrichment_prompt(bundle)

    logger.info(
        "LLM enrichment: sending %d containers (%d relationships) for review",
        len(batch), len(batch_rels),
    )

    # Temporarily extend timeout for larger generation budget
    original_timeout = getattr(llm_manager, "timeout", 30)
    try:
        llm_manager.timeout = max(original_timeout, 120)
        raw_response = llm_manager.generate_text(
            prompt,
            max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
            use_cache=True,
        )
    except Exception as exc:
        logger.warning("LLM enrichment call failed: %s", exc)
        return {"enriched": 0, "discarded": 0, "inferred_relationships": 0,
                "skipped": False, "error": str(exc)}
    finally:
        llm_manager.timeout = original_timeout

    if not raw_response:
        logger.warning("LLM enrichment: empty response from model")
        return {"enriched": 0, "discarded": 0, "inferred_relationships": 0,
                "skipped": False, "error": "empty_response"}

    llm_result = parse_llm_enrichment_response(raw_response)
    if not llm_result:
        logger.warning(
            "LLM enrichment: could not parse response (first 300 chars): %s",
            raw_response[:300],
        )
        return {"enriched": 0, "discarded": 0, "inferred_relationships": 0,
                "skipped": False, "error": "parse_failed"}

    # Apply enrichments to the full containers dict (batch keys are a subset)
    apply_enrichments(containers, relationships, llm_result)

    run_id = str(uuid4())
    for container in containers.values():
        llm_confidence = container.get("llm_confidence", 1.0)
        if llm_confidence < 0.70:
            try:
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
            except Exception as exc:
                logger.debug("Review queue insert skipped (table may not exist): %s", exc)

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
        "error": None,
    }
