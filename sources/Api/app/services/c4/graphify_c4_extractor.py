"""Graphify + OpenRouter C4 extraction pipeline.

Replaces the legacy ContextManager / ContainerManager / ComponentExtractor
triple.  The pipeline is:

  1. Run Graphify (Tree-sitter AST pass only) → graph.json
  2. Summarise graph.json into a compact LLM-friendly JSON blob
  3. Call minimax/minimax-m3 via OpenRouter → full C4 JSON
  4. Validate & map to the exact shape GraphWriter.write() expects

No changes are needed to GraphWriter, the routes, or Neo4j schema.
"""

import logging
from pathlib import Path
from typing import Any

from app.domain.exceptions import ExtractionError
from app.services.c4.graphify_runner import run_graphify
from app.services.c4.graphify_summarizer import summarize_graph
from app.services.c4.graphify_llm import build_c4_prompt, call_openrouter

logger = logging.getLogger(__name__)

_VALID_STATUS = {"ACTIVE", "MAINTENANCE", "DEPRECATED", "ARCHIVED"}
_VALID_COMPLIANCE = {"LOW_RISK", "MEDIUM_RISK", "HIGH_RISK"}
_VALID_TIERS = {"Tier 1", "Tier 2", "Tier 3", "Unknown"}
_VALID_DATA_CLASS = {"PII", "Credit-Card", "Internal", "Public", "Unknown"}
_VALID_CONTAINER_TYPES = {"service", "database", "frontend", "cache", "queue", "gateway", "worker"}
_VALID_COMPONENT_TYPES = {
    "http_handler", "database_adapter", "task_processor",
    "event_listener", "service_layer", "utility", "model",
}

# Priority order for keeping components when capping per-container.
# Lower index = higher priority = kept first.
_COMPONENT_TYPE_PRIORITY = [
    "http_handler",      # public API entry points
    "database_adapter",  # infrastructure boundaries
    "task_processor",    # background job entry points
    "event_listener",    # event-driven entry points
    "service_layer",     # public service facades
    "model",             # domain models
    "utility",           # internal helpers — dropped first
]
_MAX_COMPONENTS_PER_CONTAINER = 6


class GraphifyC4Extractor:
    """Extract C4 levels (Context, Container, Component) via Graphify + OpenRouter LLM.

    Args:
        repo_path: Absolute path to the cloned repository.
    """

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = Path(repo_path).resolve()

    def extract(self) -> dict[str, Any]:
        """Run the full Graphify → LLM → C4 pipeline.

        Returns:
            Dict matching the GraphWriter.write() c4_data contract.

        Raises:
            ExtractionError: If Graphify or the LLM call fails.
        """
        logger.info("GraphifyC4Extractor: starting for %s", self.repo_path)

        logger.info("Step 1/3: Running Graphify AST extraction…")
        graph = run_graphify(self.repo_path)
        logger.info(
            "Step 1/3 done: %d nodes, %d edges",
            len(graph.get("nodes", [])),
            len(graph.get("links", graph.get("edges", []))),
        )

        logger.info("Step 2/3: Summarising graph for LLM…")
        summary = summarize_graph(graph, repo_path=self.repo_path)

        logger.info("Step 3/3: Calling OpenRouter for C4 inference…")
        prompt = build_c4_prompt(summary)
        raw = call_openrouter(prompt)

        logger.info("Validating and mapping LLM output…")
        c4_data = _validate_and_map(raw)

        logger.info(
            "GraphifyC4Extractor done: %d containers, %d components",
            len(c4_data["containers"]),
            len(c4_data["components"]),
        )
        return c4_data


def _validate_and_map(raw: dict[str, Any]) -> dict[str, Any]:
    """Enforce enum constraints and strip unexpected keys from LLM output."""
    ctx: dict = raw.get("system_context", {})

    if ctx.get("status") not in _VALID_STATUS:
        ctx["status"] = "ACTIVE"
    if ctx.get("compliance") not in _VALID_COMPLIANCE:
        ctx["compliance"] = "MEDIUM_RISK"
    if ctx.get("tier") not in _VALID_TIERS:
        ctx["tier"] = "Unknown"
    if ctx.get("data_class") not in _VALID_DATA_CLASS:
        ctx["data_class"] = "Unknown"

    ctx.setdefault("actors", [])
    ctx.setdefault("external_dependencies", [])
    ctx.setdefault("languages", [])
    ctx.setdefault("frameworks", [])

    containers: list[dict] = []
    for c in raw.get("containers", []):
        if not c.get("name"):
            continue
        if c.get("container_type") not in _VALID_CONTAINER_TYPES:
            c["container_type"] = "service"
        c.setdefault(
            "is_infrastructure_only",
            c["container_type"] in {"database", "cache", "queue"},
        )
        c.setdefault("protocol", "HTTP")
        c.setdefault("description", "")
        c.setdefault("technology", "")
        containers.append(c)

    container_names = {c["name"] for c in containers}

    # Collect and validate components, then cap per container by priority
    raw_components: list[dict] = []
    for comp in raw.get("components", []):
        if not comp.get("name"):
            continue
        if comp.get("container") not in container_names:
            logger.debug(
                "Dropping component '%s' — unknown container '%s'",
                comp.get("name"), comp.get("container"),
            )
            continue
        if comp.get("component_type") not in _VALID_COMPONENT_TYPES:
            comp["component_type"] = "service_layer"
        comp.setdefault("type", "component")
        comp.setdefault("endpoint_path", "")
        comp.setdefault("endpoint_method", "")
        comp.setdefault("language", "")
        comp.setdefault("description", "")
        raw_components.append(comp)

    # Cap to _MAX_COMPONENTS_PER_CONTAINER, keeping highest-priority types first
    priority = {t: i for i, t in enumerate(_COMPONENT_TYPE_PRIORITY)}
    raw_components.sort(key=lambda c: priority.get(c["component_type"], 99))

    per_container: dict[str, int] = {}
    components: list[dict] = []
    for comp in raw_components:
        container = comp["container"]
        count = per_container.get(container, 0)
        if count < _MAX_COMPONENTS_PER_CONTAINER:
            components.append(comp)
            per_container[container] = count + 1
        else:
            logger.debug(
                "Capping components for '%s': dropping '%s' (%s)",
                container, comp["name"], comp["component_type"],
            )

    rels: dict = raw.get("relationships", {})

    return {
        "c4_model_version": "1.0",
        "system_context": ctx,
        "containers": containers,
        "components": components,
        "relationships": {
            "context": rels.get("context", []),
            "containers": rels.get("containers", []),
            "components": rels.get("components", []),
        },
        "metadata": {
            "total_containers": len(containers),
            "total_components": len(components),
            "extraction_approach": "graphify_llm",
            "runtime": {},
        },
    }
