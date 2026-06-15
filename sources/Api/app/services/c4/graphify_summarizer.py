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
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_GOD_NODE_LIMIT = 30
_COMMUNITY_LIMIT = 15
_COMMUNITY_SAMPLE = 10
_EXTERNAL_IMPORT_LIMIT = 50
_DOC_NODE_LIMIT = 10
_CROSS_DIR_EDGE_LIMIT = 40   # max cross-directory call/import edges in summary
_SHELL_REF_LIMIT = 20        # max inter-service references extracted from shell/config
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
    "Dockerfile": "Docker",
}

# Workspace/meta-manifest files: their presence at root means the root
# pyproject.toml/package.json etc. is a workspace descriptor, not a service.
_WORKSPACE_MARKERS = {"workspace.toml", "pnpm-workspace.yaml", "nx.json", "lerna.json", "rush.json"}

# Directory names that are monorepo project aggregators — scan one level deeper inside them.
_MONOREPO_PROJECT_DIRS = {"projects", "apps", "services", "packages", "crates"}

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


def _classify_dir(name: str) -> str:
    return _NON_CONTAINER_DIR_HINTS.get(name.lower(), "service")


def _scan_dir_for_manifest(directory: Path, rel_prefix: str, procfile_entries: dict) -> dict | None:
    """Return a deployment_unit entry if *directory* contains a runtime manifest."""
    for manifest, runtime in _RUNTIME_MANIFESTS.items():
        if (directory / manifest).exists():
            rel_path = f"{rel_prefix}/{directory.name}" if rel_prefix else directory.name
            entry: dict = {
                "path": rel_path,
                "runtime": runtime,
                "manifest": manifest,
                "likely_role": _classify_dir(directory.name),
            }
            for proc_name, cmd in procfile_entries.items():
                if directory.name in cmd or directory.name == proc_name:
                    entry["procfile_process"] = proc_name
                    entry["procfile_cmd"] = cmd
                    break
            return entry
    return None


def detect_deployment_units(repo_path: Path) -> list[dict]:
    """Scan repo for directories that contain their own runtime manifests.

    Scans root, one level deep, and two levels deep inside known monorepo
    aggregator directories (projects/, apps/, services/, packages/, crates/).
    Also detects Dockerfile-only deployable units and workspace roots.

    Returns a list of dicts: {path, runtime, manifest, likely_role}.
    These are strong signals for C4 container boundaries.
    """
    units: list[dict] = []
    seen_paths: set[str] = set()

    # Check root-level Procfile for explicit process definitions
    procfile_entries: dict[str, str] = {}
    procfile = repo_path / "Procfile"
    if procfile.exists():
        for line in procfile.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ":" in line:
                name, _, cmd = line.partition(":")
                procfile_entries[name.strip()] = cmd.strip()

    # Detect workspace root: if a workspace marker exists alongside the root
    # manifest, mark the root as a workspace aggregator, not a deployable.
    is_workspace_root = any((repo_path / m).exists() for m in _WORKSPACE_MARKERS)

    # Root dir itself
    for manifest, runtime in _RUNTIME_MANIFESTS.items():
        if (repo_path / manifest).exists():
            role = "workspace" if is_workspace_root else "service"
            units.append({
                "path": ".",
                "runtime": runtime,
                "manifest": manifest,
                "likely_role": role,
            })
            seen_paths.add(".")
            break

    # One level deep + two levels deep inside monorepo aggregator dirs
    for child in sorted(repo_path.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue

        entry = _scan_dir_for_manifest(child, "", procfile_entries)
        if entry and entry["path"] not in seen_paths:
            units.append(entry)
            seen_paths.add(entry["path"])

        # Recurse up to two more levels inside known monorepo aggregator dirs
        # to handle nested project layouts (e.g. services/gateway/cmd/).
        if child.name.lower() in _MONOREPO_PROJECT_DIRS:
            for grandchild in sorted(child.iterdir()):
                if not grandchild.is_dir() or grandchild.name.startswith("."):
                    continue
                g_entry = _scan_dir_for_manifest(grandchild, child.name, procfile_entries)
                if g_entry and g_entry["path"] not in seen_paths:
                    units.append(g_entry)
                    seen_paths.add(g_entry["path"])
                else:
                    # No manifest at this level — go one more level deeper.
                    for ggchild in sorted(grandchild.iterdir()):
                        if not ggchild.is_dir() or ggchild.name.startswith("."):
                            continue
                        gg_entry = _scan_dir_for_manifest(
                            ggchild, f"{child.name}/{grandchild.name}", procfile_entries
                        )
                        if gg_entry and gg_entry["path"] not in seen_paths:
                            units.append(gg_entry)
                            seen_paths.add(gg_entry["path"])

    # Include all Procfile entries as supplementary signal
    if procfile_entries:
        units.append({"procfile": procfile_entries})

    return units


def _top_dir(source_file: str) -> str:
    """Return the top-level directory of a source file path (first path component)."""
    parts = Path(source_file).parts
    return parts[0] if parts else ""


def extract_cross_dir_edges(
    nodes: list[dict], links: list[dict], limit: int = _CROSS_DIR_EDGE_LIMIT
) -> list[dict]:
    """Extract call/import edges that cross top-level directory boundaries.

    These are the strongest structural signal for inter-container dependencies:
    a cross-directory import or call indicates a real code dependency between
    two deployment units.  Pure within-module edges (same top-level dir) are
    noise for container-boundary inference.
    """
    node_by_id: dict[str, dict] = {n["id"]: n for n in nodes}

    # Count occurrences of each cross-dir pair so we can rank by frequency
    pair_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    pair_example: dict[tuple[str, str, str], tuple[str, str]] = {}

    for link in links:
        relation = link.get("relation", "")
        if relation not in ("imports", "calls", "uses", "inherits"):
            continue
        src_node = node_by_id.get(link.get("source", ""), {})
        tgt_node = node_by_id.get(link.get("target", ""), {})
        src_file = src_node.get("source_file", "")
        tgt_file = tgt_node.get("source_file", "")
        if not src_file or not tgt_file:
            continue
        src_dir = _top_dir(src_file)
        tgt_dir = _top_dir(tgt_file)
        if not src_dir or not tgt_dir or src_dir == tgt_dir:
            continue
        key = (src_dir, tgt_dir, relation)
        pair_counts[key] += 1
        if key not in pair_example:
            pair_example[key] = (
                src_node.get("label", src_file),
                tgt_node.get("label", tgt_file),
            )

    results = []
    for (src_dir, tgt_dir, relation), count in sorted(
        pair_counts.items(), key=lambda x: -x[1]
    )[:limit]:
        src_label, tgt_label = pair_example[(src_dir, tgt_dir, relation)]
        results.append({
            "from_dir": src_dir,
            "to_dir": tgt_dir,
            "relation": relation,
            "occurrences": count,
            "example": f"{src_label} → {tgt_label}",
        })
    return results


# Patterns that reveal inter-service calls in shell scripts and config files
_SHELL_URL_RE = re.compile(
    r'(?:curl|wget|fetch|http_get|http_post)\s+["\']?(https?://[^\s"\']+)', re.I
)
_KUBECTL_NS_RE = re.compile(
    r'(?:kubectl|KUBECTL)\s+(?:apply|create|delete|get|patch|label|annotate)[^\n]*?-n\s+["\']?(\S+)', re.I
)
_ENV_URL_RE = re.compile(r'[A-Z_]+_(?:URL|HOST|ENDPOINT|ADDR)\s*[=:]\s*["\']?(https?://[^\s"\']+)', re.I)


def extract_shell_references(repo_path: Path, limit: int = _SHELL_REF_LIMIT) -> list[dict]:
    """Scan shell scripts and env files for inter-service call patterns.

    Surfaces kubectl namespace references, HTTP endpoint calls, and
    environment variable URL assignments that reveal runtime dependencies
    invisible to the AST pass (e.g. tunnel-handler.sh calling kubectl to
    create a Service that another controller watches).
    """
    refs: list[dict] = []
    seen: set[str] = set()

    shell_extensions = {".sh", ".bash", ".env", ".envrc", "Makefile", "makefile"}

    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in shell_extensions and path.name not in shell_extensions:
            continue
        if any(p.startswith(".") or p in (".venv", "venv", "node_modules") for p in path.parts):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        rel = str(path.relative_to(repo_path))
        top_dir = _top_dir(rel)

        for m in _KUBECTL_NS_RE.finditer(text):
            namespace = m.group(1).strip()
            key = f"kubectl:{top_dir}:{namespace}"
            if key not in seen and len(refs) < limit:
                seen.add(key)
                refs.append({"file": rel, "type": "kubectl_namespace", "reference": namespace})

        for m in _SHELL_URL_RE.finditer(text):
            url = m.group(1).strip().rstrip("'\"")
            key = f"url:{top_dir}:{url}"
            if key not in seen and len(refs) < limit:
                seen.add(key)
                refs.append({"file": rel, "type": "http_call", "reference": url})

        for m in _ENV_URL_RE.finditer(text):
            val = m.group(1).strip()
            if len(val) > 5:
                key = f"env:{top_dir}:{val}"
                if key not in seen and len(refs) < limit:
                    seen.add(key)
                    refs.append({"file": rel, "type": "env_url", "reference": val})

    return refs


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

    # Cross-directory call/import edges — strongest signal for inter-container deps
    cross_dir_edges = extract_cross_dir_edges(nodes, links)

    # Deployment units — filesystem signal for container boundaries
    deployment_units: list[dict] = []
    shell_references: list[dict] = []
    if repo_path is not None:
        try:
            deployment_units = detect_deployment_units(Path(repo_path))
        except Exception as exc:
            logger.warning("Deployment unit detection failed: %s", exc)
        try:
            shell_references = extract_shell_references(Path(repo_path))
        except Exception as exc:
            logger.warning("Shell reference extraction failed: %s", exc)

    summary = {
        "stats": {"nodes": len(nodes), "edges": len(links)},
        "deployment_units": deployment_units,
        "cross_dir_edges": cross_dir_edges,
        "shell_references": shell_references,
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
