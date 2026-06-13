"""Compress a Graphify graph.json into a compact summary for LLM context.

The raw graph can contain tens of thousands of nodes and edges — far too large
for a single LLM call.  This module extracts the structural signals that are
most useful for inferring C4 levels:

  - Deployment units (dirs with their own runtime manifests → container boundaries)
  - God nodes (highest degree → most important abstractions)
  - Community clusters (Leiden groups → natural container/component boundaries)
  - External imports (packages with no source_file → external dependencies)
  - Language distribution (file extension counts)
  - Document nodes (README, configs → owner/purpose hints)
"""

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_GOD_NODE_LIMIT = 30
_COMMUNITY_LIMIT = 15
_COMMUNITY_SAMPLE = 10
_EXTERNAL_IMPORT_LIMIT = 50
_DOC_NODE_LIMIT = 10
_TARGET_CHARS = 32_000  # ~8k tokens at 4 chars/token

# Runtime manifests that indicate a separately deployable unit
_RUNTIME_MANIFESTS = {
    "package.json": "Node.js",
    "Gemfile": "Ruby",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "pyproject.toml": "Python",
    "setup.py": "Python",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java/Kotlin (Gradle)",
    "mix.exs": "Elixir",
}

# Directory names that strongly indicate non-runtime purposes.
# Used to annotate deployment_units so the LLM can exclude them as containers.
_NON_CONTAINER_DIR_HINTS: dict[str, str] = {
    # Build tooling
    "buildsrc": "build_tooling",
    "gradle": "build_tooling",
    "cmake": "build_tooling",
    "tools": "build_tooling",
    "scripts": "build_tooling",
    "hack": "build_tooling",
    "make": "build_tooling",
    # Documentation
    "docs": "documentation",
    "documentation": "documentation",
    "docusaurus": "documentation",
    "storybook": "documentation",
    "mkdocs": "documentation",
    "wiki": "documentation",
    "site": "documentation",
    # CI/CD
    ".github": "ci_cd",
    ".circleci": "ci_cd",
    ".gitlab": "ci_cd",
    # IaC
    "terraform": "iac",
    "k8s": "iac",
    "kubernetes": "iac",
    "helm": "iac",
    "charts": "iac",
    "infra": "iac",
    "deploy": "iac",
    "pulumi": "iac",
    # Test suites
    "e2e": "test_suite",
    "tests": "test_suite",
    "test": "test_suite",
    "spec": "test_suite",
    "cypress": "test_suite",
    "playwright": "test_suite",
    "fixtures": "test_suite",
    # Shared libraries (no network boundary)
    "lib": "shared_library",
    "libs": "shared_library",
    "sdk": "shared_library",
    "shared": "shared_library",
    "common": "shared_library",
    "packages": "shared_library",
    "modules": "shared_library",
}


def detect_deployment_units(repo_path: Path) -> list[dict]:
    """Scan repo for directories that contain their own runtime manifests.

    Returns a list of dicts: {path, runtime, manifest, procfile_entry}.
    These are strong signals for C4 container boundaries.
    """
    units: list[dict] = []

    # Check root-level Procfile for explicit process definitions
    procfile_entries: dict[str, str] = {}
    procfile = repo_path / "Procfile"
    if procfile.exists():
        for line in procfile.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ":" in line:
                name, _, cmd = line.partition(":")
                procfile_entries[name.strip()] = cmd.strip()

    # Root dir itself
    for manifest, runtime in _RUNTIME_MANIFESTS.items():
        if (repo_path / manifest).exists():
            units.append({
                "path": ".",
                "runtime": runtime,
                "manifest": manifest,
                "likely_role": "service",
            })
            break  # one entry per dir

    # One level deep
    for child in sorted(repo_path.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        for manifest, runtime in _RUNTIME_MANIFESTS.items():
            if (child / manifest).exists():
                entry = {
                    "path": child.name,
                    "runtime": runtime,
                    "manifest": manifest,
                }
                # Annotate likely non-container dirs so the LLM can exclude them
                hint = _NON_CONTAINER_DIR_HINTS.get(child.name.lower())
                if hint:
                    entry["likely_role"] = hint
                else:
                    entry["likely_role"] = "service"
                # Attach matching Procfile process name if found
                for proc_name, cmd in procfile_entries.items():
                    if child.name in cmd or child.name == proc_name:
                        entry["procfile_process"] = proc_name
                        entry["procfile_cmd"] = cmd
                        break
                units.append(entry)
                break

    # Include all Procfile entries as supplementary signal
    if procfile_entries:
        units.append({"procfile": procfile_entries})

    return units


def summarize_graph(graph: dict[str, Any], repo_path: Path | None = None) -> str:
    """Return a compact JSON string summarising the Graphify graph for an LLM.

    Args:
        graph: Parsed graph.json dict from Graphify.
        repo_path: Optional path to the cloned repo; enables deployment unit detection.

    Returns:
        Compact JSON string, targeting ~8k tokens.
    """
    nodes: list[dict] = graph.get("nodes", [])
    links: list[dict] = graph.get("links", graph.get("edges", []))

    node_by_id: dict[str, dict] = {n["id"]: n for n in nodes}

    # Node degree (undirected)
    degree: dict[str, int] = defaultdict(int)
    for link in links:
        degree[link.get("source", "")] += 1
        degree[link.get("target", "")] += 1

    # God nodes: top N by degree
    god_nodes = sorted(nodes, key=lambda n: degree[n["id"]], reverse=True)[:_GOD_NODE_LIMIT]

    # External imports: import edges where target has no source_file
    external: set[str] = set()
    for link in links:
        if link.get("relation") == "imports":
            target = node_by_id.get(link.get("target", ""), {})
            if not target.get("source_file"):
                external.add(target.get("label", link.get("target", "")))

    # Community clusters
    community_members: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        c = node.get("community")
        if c is not None:
            community_members[c].append(node.get("label", node["id"]))

    communities = {
        str(c_id): {"size": len(members), "sample": members[:_COMMUNITY_SAMPLE]}
        for c_id, members in sorted(
            community_members.items(), key=lambda x: -len(x[1])
        )[:_COMMUNITY_LIMIT]
    }

    # Language distribution from file extensions
    ext_counts = Counter(
        Path(n["source_file"]).suffix.lstrip(".").lower()
        for n in nodes
        if n.get("source_file")
    )

    # Document nodes (README, configs)
    doc_nodes = [
        n.get("label", n["id"])
        for n in nodes
        if n.get("file_type") == "document"
    ][:_DOC_NODE_LIMIT]

    # Deployment units — filesystem signal for container boundaries
    deployment_units: list[dict] = []
    if repo_path is not None:
        try:
            deployment_units = detect_deployment_units(Path(repo_path))
        except Exception as exc:
            logger.warning("Deployment unit detection failed: %s", exc)

    summary = {
        "stats": {"nodes": len(nodes), "edges": len(links)},
        "deployment_units": deployment_units,
        "god_nodes": [
            {
                "label": n.get("label"),
                "degree": degree[n["id"]],
                "file": n.get("source_file"),
                "type": n.get("file_type"),
            }
            for n in god_nodes
        ],
        "communities": communities,
        "external_imports": sorted(external)[:_EXTERNAL_IMPORT_LIMIT],
        "languages": dict(ext_counts.most_common(10)),
        "doc_nodes": doc_nodes,
    }

    result = json.dumps(summary, indent=2)

    if len(result) > _TARGET_CHARS:
        logger.warning(
            "Graph summary is %d chars (> %d target) — truncating god_nodes",
            len(result), _TARGET_CHARS,
        )
        summary["god_nodes"] = summary["god_nodes"][:15]
        result = json.dumps(summary, indent=2)

    logger.info("Graph summary: %d chars", len(result))
    return result
