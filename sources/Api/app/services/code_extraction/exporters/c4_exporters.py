"""C4 architecture exporters (Structurizr DSL and Mermaid C4)."""

from __future__ import annotations

import re
from typing import Any


def _safe_id(value: str) -> str:
    """Return a safe identifier for DSL formats."""
    base = re.sub(r"[^a-zA-Z0-9_]", "_", str(value or "").strip())
    if not base:
        return "node"
    if base[0].isdigit():
        base = f"n_{base}"
    return re.sub(r"_+", "_", base)


def _safe_label(value: str) -> str:
    return str(value or "").replace('"', '\\"').strip() or "Unknown"


def _safe_tag(value: str) -> str:
    """Normalize a Structurizr tag token (no commas/quotes)."""
    token = str(value or "").replace('"', "").replace(",", " ").strip()
    token = re.sub(r"\s+", "-", token)
    return token


def _build_metadata_tags(payload: dict[str, Any]) -> list[str]:
    """Build normalized metadata tags for Structurizr elements."""
    tags: list[str] = []
    attributes = payload.get("attributes")
    attrs = attributes if isinstance(attributes, dict) else {}

    domain = payload.get("domain") or attrs.get("domain")
    if domain:
        tags.append(f"Domain:{_safe_tag(str(domain))}")

    squad = payload.get("squad") or attrs.get("squad")
    if squad:
        tags.append(f"Squad:{_safe_tag(str(squad))}")

    sensitivity_tags = payload.get("sensitivity_tags") or attrs.get("sensitivity_tags") or []
    if isinstance(sensitivity_tags, list):
        for sensitivity in sensitivity_tags:
            if sensitivity:
                tags.append(f"Sensitivity:{_safe_tag(str(sensitivity))}")

    # Backward compatibility fallback.
    if not sensitivity_tags:
        data_class = payload.get("data_class") or attrs.get("data_class")
        if data_class and str(data_class).lower() != "general":
            tags.append(f"Sensitivity:{_safe_tag(str(data_class))}")

    seen: set[str] = set()
    deduped: list[str] = []
    for tag in tags:
        if tag and tag not in seen:
            seen.add(tag)
            deduped.append(tag)
    return deduped


def export_structurizr_dsl(c4_data: dict[str, Any]) -> str:
    """Export minimal Structurizr DSL workspace from current C4 payload."""
    system_context = c4_data.get("system_context") or {}
    containers = c4_data.get("containers") or []
    rels = (c4_data.get("relationships") or {}).get("containers") or []

    system_name = _safe_label(system_context.get("name") or "System")
    system_desc = _safe_label(system_context.get("description") or system_context.get("purpose") or "System context")

    lines: list[str] = []
    lines.append("workspace {")
    lines.append('  model {')
    lines.append(f'    system = softwareSystem "{system_name}" "{system_desc}" {{')

    system_tags = _build_metadata_tags(system_context)
    all_tags: set[str] = set(system_tags)
    if system_tags:
        lines.append(f'      tags "{",".join(system_tags)}"')
    lines.append("    }")

    container_ids: dict[str, str] = {}
    for idx, container in enumerate(containers):
        name = _safe_label(container.get("name") or f"Container {idx + 1}")
        cid = _safe_id(f"container_{idx}_{name}")
        tech = _safe_label(container.get("technology") or "Unknown")
        desc = _safe_label(container.get("description") or container.get("container_type") or "Container")
        lines.append(f'    {cid} = container system "{name}" "{desc}" "{tech}" {{')
        container_tags = _build_metadata_tags(container)
        all_tags.update(container_tags)
        if container_tags:
            lines.append(f'      tags "{",".join(container_tags)}"')
        lines.append("    }")
        container_ids[name] = cid

    for rel in rels:
        src_name = str(rel.get("from") or rel.get("source") or "").strip()
        dst_name = str(rel.get("to") or rel.get("destination") or "").strip()
        if not src_name or not dst_name:
            continue
        src_id = container_ids.get(src_name)
        dst_id = container_ids.get(dst_name)
        if not src_id or not dst_id:
            continue
        label = _safe_label(rel.get("description") or rel.get("relationship_type") or "uses")
        lines.append(f'    {src_id} -> {dst_id} "{label}"')

    lines.append("  }")
    lines.append("  views {")
    lines.append("    systemContext system {")
    lines.append("      include *")
    lines.append("      autoLayout lr")
    lines.append("    }")
    lines.append("    container system {")
    lines.append("      include *")
    lines.append("      autoLayout lr")
    lines.append("    }")
    lines.append("    styles {")
    lines.append('      element "Software System" {')
    lines.append('        background "#1168bd"')
    lines.append('        color "#ffffff"')
    lines.append("      }")
    lines.append('      element "Container" {')
    lines.append('        background "#438dd5"')
    lines.append('        color "#ffffff"')
    lines.append("      }")

    if any(tag.startswith("Sensitivity:PII") for tag in all_tags):
        lines.append('      element "Sensitivity:PII" {')
        lines.append('        background "#b91c1c"')
        lines.append('        color "#ffffff"')
        lines.append("      }")
    if any(tag.startswith("Sensitivity:PCI") for tag in all_tags):
        lines.append('      element "Sensitivity:PCI" {')
        lines.append('        background "#7f1d1d"')
        lines.append('        color "#ffffff"')
        lines.append("      }")
    if any(tag.startswith("Sensitivity:Financial") for tag in all_tags):
        lines.append('      element "Sensitivity:Financial" {')
        lines.append('        background "#9a3412"')
        lines.append('        color "#ffffff"')
        lines.append("      }")
    if any(tag.startswith("Sensitivity:Security") for tag in all_tags):
        lines.append('      element "Sensitivity:Security" {')
        lines.append('        background "#334155"')
        lines.append('        color "#ffffff"')
        lines.append("      }")

    lines.append("    }")
    lines.append("    theme default")
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def export_mermaid_c4(c4_data: dict[str, Any]) -> str:
    """Export Mermaid C4Context diagram snippet from current C4 payload."""
    system_context = c4_data.get("system_context") or {}
    deps = system_context.get("external_dependencies") or []

    system_name = _safe_label(system_context.get("name") or "System")
    system_desc = _safe_label(system_context.get("description") or system_context.get("purpose") or "System")
    sys_id = _safe_id(f"system_{system_name}")

    lines: list[str] = []
    lines.append("C4Context")
    lines.append(f'    title {_safe_label(system_name)} - Context')
    lines.append("")
    lines.append("    %% Metadata")
    lines.extend(_render_mermaid_metadata_comments("System", system_context))
    lines.append(f'    System({sys_id}, "{system_name}", "{system_desc}")')

    for idx, dep in enumerate(deps):
        dep_name = _safe_label(dep.get("name") or f"External {idx + 1}")
        dep_id = _safe_id(f"external_{idx}_{dep_name}")
        dep_desc = _safe_label(dep.get("type") or dep.get("dependency_type") or "External System")
        lines.extend(_render_mermaid_metadata_comments(dep_name, dep))
        lines.append(f'    System_Ext({dep_id}, "{dep_name}", "{dep_desc}")')
        lines.append(f'    Rel({sys_id}, {dep_id}, "uses")')

    return "\n".join(lines) + "\n"


def _render_mermaid_metadata_comments(node_name: str, payload: dict[str, Any]) -> list[str]:
    """Render metadata as Mermaid comments for portability/readability."""
    tags = _build_metadata_tags(payload)
    if not tags:
        return []

    comments = [f"    %% {node_name} tags: {', '.join(tags)}"]
    return comments
