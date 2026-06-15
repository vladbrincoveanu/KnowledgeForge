"""IaC-aware C4 extraction for repos with no parseable source code.

Handles GitOps repos (Helm charts, ArgoCD Applications, Kustomize overlays)
and Docker Compose stacks.  Builds a structured summary and calls the same
OpenRouter LLM pipeline used by the Graphify path.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# How much of values.yaml to read (bytes) — avoid huge files
_VALUES_READ_LIMIT = 4096


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

def _try_load_yaml(path: Path) -> dict | list | None:
    try:
        import yaml  # type: ignore[import-untyped]
        text = path.read_text(encoding="utf-8", errors="ignore")
        return yaml.safe_load(text)
    except Exception as exc:
        logger.debug("Could not parse %s: %s", path, exc)
        return None


def _read_helm_chart(chart_yaml: Path) -> dict:
    """Return a dict describing a Helm chart from its Chart.yaml."""
    data = _try_load_yaml(chart_yaml) or {}
    deps = []
    for dep in data.get("dependencies", []):
        if isinstance(dep, dict) and dep.get("name"):
            deps.append(dep["name"])

    # Grab image name from values.yaml if present
    values_file = chart_yaml.parent / "values.yaml"
    image_ref = ""
    if values_file.exists():
        try:
            text = values_file.read_text(encoding="utf-8", errors="ignore")[:_VALUES_READ_LIMIT]
            import re
            m = re.search(r'repository:\s*([^\s\n]+)', text)
            if m:
                image_ref = m.group(1).strip()
        except Exception:
            pass

    return {
        "name": data.get("name", chart_yaml.parent.parent.name),
        "description": data.get("description", ""),
        "version": data.get("appVersion", data.get("version", "")),
        "chart_path": str(chart_yaml.parent.relative_to(chart_yaml.parents[3])),
        "dependencies": deps,
        "image": image_ref,
    }


def _read_argocd_app(app_yaml: Path) -> dict | None:
    """Return a dict for an ArgoCD Application manifest, or None if not one."""
    data = _try_load_yaml(app_yaml)
    if not isinstance(data, dict):
        return None
    if data.get("kind") != "Application":
        return None
    spec = data.get("spec", {})
    dest = spec.get("destination", {})
    source = spec.get("source", spec.get("sources", [{}])[0] if isinstance(spec.get("sources"), list) else {})
    if isinstance(source, list):
        source = source[0] if source else {}
    return {
        "name": data.get("metadata", {}).get("name", app_yaml.stem),
        "namespace": dest.get("namespace", ""),
        "chart": source.get("chart", ""),
        "repo_url": source.get("repoURL", ""),
        "target_revision": source.get("targetRevision", ""),
    }


def _read_kustomize(kustomization: Path) -> dict:
    """Return a dict describing a Kustomize component."""
    data = _try_load_yaml(kustomization) or {}
    resources = data.get("resources", data.get("bases", []))
    patches = [p if isinstance(p, str) else p.get("path", "") for p in data.get("patches", [])]
    return {
        "project": kustomization.parents[1].name,
        "resources": [str(r) for r in resources if r][:10],
        "patches": [p for p in patches if p][:5],
    }


def _read_docker_compose(compose_file: Path) -> list[dict]:
    """Return a list of service dicts from a docker-compose file."""
    data = _try_load_yaml(compose_file) or {}
    services = []
    for svc_name, svc in (data.get("services") or {}).items():
        if not isinstance(svc, dict):
            continue
        services.append({
            "name": svc_name,
            "image": svc.get("image", ""),
            "ports": svc.get("ports", [])[:4],
            "depends_on": list(svc.get("depends_on", {}).keys()) if isinstance(svc.get("depends_on"), dict)
                         else svc.get("depends_on", []),
        })
    return services


# ---------------------------------------------------------------------------
# Repo scan
# ---------------------------------------------------------------------------

def _scan_iac_repo(repo_path: Path) -> dict[str, Any]:
    """Walk repo_path and collect all IaC signals."""
    helm_charts: list[dict] = []
    argocd_apps: list[dict] = []
    kustomize_components: list[dict] = []
    compose_services: list[dict] = []

    seen_charts: set[str] = set()

    for path in sorted(repo_path.rglob("*")):
        # Skip hidden dirs and virtual envs
        parts = path.parts
        if any(p.startswith(".") or p in (".venv", "venv", "node_modules", "vendor") for p in parts):
            continue

        if not path.is_file():
            continue

        name = path.name.lower()

        if name == "chart.yaml":
            entry = _read_helm_chart(path)
            key = entry["chart_path"]
            if key not in seen_charts:
                helm_charts.append(entry)
                seen_charts.add(key)

        elif name in ("kustomization.yaml", "kustomization.yml"):
            kustomize_components.append(_read_kustomize(path))

        elif name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            compose_services.extend(_read_docker_compose(path))

        elif name.endswith(".yaml") or name.endswith(".yml"):
            app = _read_argocd_app(path)
            if app:
                argocd_apps.append(app)

    return {
        "helm_charts": helm_charts,
        "argocd_apps": argocd_apps,
        "kustomize_components": kustomize_components,
        "compose_services": compose_services,
    }


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def summarize_iac(repo_path: Path) -> str:
    """Build a compact JSON summary of the IaC repo for LLM context."""
    import json

    signals = _scan_iac_repo(repo_path)

    # Derive environments from values file names (values-dev.yaml, values-prod.yaml)
    # and ArgoCD app namespaces / gitops file names
    envs: set[str] = set()
    _env_keywords = {"dev": "dev", "prod": "prod", "production": "prod", "staging": "staging"}
    for chart in signals["helm_charts"]:
        for kw, env in _env_keywords.items():
            if kw in chart.get("chart_path", ""):
                envs.add(env)
    for app in signals["argocd_apps"]:
        for field in (app.get("namespace", ""), app.get("name", "")):
            for kw, env in _env_keywords.items():
                if kw in field:
                    envs.add(env)
    # Also scan file names across the repo
    for path in repo_path.rglob("values-*.yaml"):
        stem = path.stem.replace("values-", "")
        mapped = _env_keywords.get(stem)
        if mapped:
            envs.add(mapped)

    # README for context
    readme_hint = ""
    for readme in (repo_path / "README.md", repo_path / "readme.md"):
        if readme.exists():
            try:
                readme_hint = readme.read_text(encoding="utf-8", errors="ignore")[:2000]
            except Exception:
                pass
            break

    summary: dict[str, Any] = {
        "iac_type": _infer_iac_type(signals),
        "environments": sorted(envs) or ["unknown"],
        "helm_charts": signals["helm_charts"],
        "argocd_apps": signals["argocd_apps"],
        "kustomize_components": signals["kustomize_components"],
        "compose_services": signals["compose_services"],
        "readme_excerpt": readme_hint,
    }

    return json.dumps(summary, indent=2)


def _infer_iac_type(signals: dict) -> str:
    parts = []
    if signals["helm_charts"]:
        parts.append("helm")
    if signals["argocd_apps"]:
        parts.append("argocd_gitops")
    if signals["kustomize_components"]:
        parts.append("kustomize")
    if signals["compose_services"]:
        parts.append("docker_compose")
    return "+".join(parts) if parts else "unknown"


# ---------------------------------------------------------------------------
# Repo classification
# ---------------------------------------------------------------------------

_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".kt", ".rb", ".cs", ".cpp", ".c", ".swift", ".scala",
}
_IAC_EXTENSIONS = {".yaml", ".yml", ".tf", ".hcl", ".toml"}
_IAC_FILENAMES = {
    "Chart.yaml", "kustomization.yaml", "kustomization.yml",
    "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
    "Dockerfile",
}


def is_iac_repo(repo_path: Path) -> bool:
    """Return True when repo has negligible source code but meaningful IaC content."""
    code_count = 0
    iac_count = 0

    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        parts = path.parts
        if any(p.startswith(".") or p in (".venv", "venv", "node_modules", "__pycache__") for p in parts):
            continue
        ext = path.suffix.lower()
        if ext in _CODE_EXTENSIONS:
            code_count += 1
        if ext in _IAC_EXTENSIONS or path.name in _IAC_FILENAMES:
            iac_count += 1

    logger.info("IaC repo check: code=%d iac=%d", code_count, iac_count)
    return code_count < 10 and iac_count >= 3
