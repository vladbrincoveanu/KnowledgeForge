"""LLM-based enrichment for C4 architecture descriptions.

Generates human-readable descriptions for nodes and edges
in the C4 architecture graph, with heuristic fallbacks.
"""

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


def clean_llm_sentence(text: Optional[str]) -> str:
    """Clean LLM output into a single sentence."""
    if not text:
        return ""
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'<.*?>', '', cleaned)
    cleaned = cleaned.strip()
    if not cleaned:
        return ""
    if len(cleaned) > 400:
        cleaned = cleaned[:400].rsplit(' ', 1)[0] + '...'
    if cleaned[-1] not in {'.', '!', '?'}:
        cleaned += '.'
    return cleaned


def describe_node_heuristic(node: dict[str, Any]) -> str:
    """Create a node description without LLM."""
    name = node.get('name') or 'This node'
    node_type = node.get('type') or node.get('component') or 'component'

    if node_type == 'system':
        return node.get('purpose') or node.get('description') or f"{name} is the main system in this repository."

    if node_type == 'component':
        method = node.get('endpoint_method')
        path = node.get('endpoint_path')
        if method and path:
            return f"{name} is an API endpoint handling {method} {path}."
        return f"{name} is a component within the system."

    container_type = node.get('container_type')
    technology = node.get('technology')
    deployment = node.get('deployment')
    details = ", ".join([v for v in [container_type, technology, deployment] if v])
    details_text = f" ({details})" if details else ""
    return f"{name} is a deployable service{details_text}."


def generate_node_description(node: dict[str, Any], llm_manager: Any = None) -> str:
    """Generate a node description using LLM or heuristic fallback."""
    if llm_manager is None:
        return describe_node_heuristic(node)

    context = {
        "name": node.get("name"),
        "type": node.get("type"),
        "container_type": node.get("container_type"),
        "technology": node.get("technology"),
        "deployment": node.get("deployment"),
        "path": node.get("path") or node.get("file"),
        "endpoint_method": node.get("endpoint_method"),
        "endpoint_path": node.get("endpoint_path"),
        "purpose": node.get("purpose"),
        "description": node.get("description"),
    }

    prompt = (
        "You are a software architecture assistant. "
        "Write 1-2 concise sentences describing what this node is used for, "
        "based only on the provided metadata. Avoid speculation.\n\n"
        f"Node metadata: {json.dumps(context, ensure_ascii=False)}"
    )

    try:
        response = llm_manager.generate_text(prompt, max_tokens=90, temperature=0.3, use_cache=True)
        cleaned = clean_llm_sentence(response)
        return cleaned or describe_node_heuristic(node)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.debug(f"LLM node description failed: {exc}")
        return describe_node_heuristic(node)


def describe_edge_heuristic(relationship: dict[str, Any]) -> str:
    """Create an edge description without LLM."""
    source = relationship.get('from') or relationship.get('source') or 'Source'
    target = relationship.get('to') or relationship.get('destination') or 'Target'
    rel_type = relationship.get('type') or relationship.get('relationship_type') or 'uses'
    protocol = relationship.get('protocol')
    protocol_text = f" over {protocol}" if protocol else ""
    return f"{source} {rel_type} {target}{protocol_text}."


def generate_edge_description(relationship: dict[str, Any], llm_manager: Any = None) -> str:
    """Generate an edge description using LLM or heuristic fallback."""
    if llm_manager is None:
        return describe_edge_heuristic(relationship)

    context = {
        "source": relationship.get('from') or relationship.get('source'),
        "target": relationship.get('to') or relationship.get('destination'),
        "relationship_type": relationship.get('type') or relationship.get('relationship_type'),
        "protocol": relationship.get('protocol'),
    }
    prompt = (
        "You are a software architecture assistant. "
        "Write 1 concise sentence describing the interaction between these two nodes. "
        "If protocol is provided, mention it.\n\n"
        f"Edge metadata: {json.dumps(context, ensure_ascii=False)}"
    )

    try:
        response = llm_manager.generate_text(prompt, max_tokens=60, temperature=0.3, use_cache=True)
        cleaned = clean_llm_sentence(response)
        return cleaned or describe_edge_heuristic(relationship)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.debug(f"LLM edge description failed: {exc}")
        return describe_edge_heuristic(relationship)


def enrich_with_llm_descriptions(
    system_context: dict,
    containers: dict,
    components: dict,
    context_relationships: list,
    container_relationships: list,
    llm_manager: Any = None,
) -> None:
    """Enrich all C4 elements with LLM-generated descriptions."""
    if system_context:
        if not system_context.get('description') and system_context.get('purpose'):
            system_context['description'] = system_context.get('purpose')
        system_context['llm_description'] = generate_node_description(system_context, llm_manager)

    for container in containers.values():
        container.setdefault('type', 'container')
        container['llm_description'] = generate_node_description(container, llm_manager)

    for component in components.values():
        component.setdefault('type', 'component')
        component['llm_description'] = generate_node_description(component, llm_manager)

    for relationship in context_relationships:
        if not relationship.get('description'):
            relationship['description'] = generate_edge_description(relationship, llm_manager)
        relationship['llm_description'] = generate_edge_description(relationship, llm_manager)

    for relationship in container_relationships:
        if not relationship.get('description'):
            relationship['description'] = generate_edge_description(relationship, llm_manager)
        relationship['llm_description'] = generate_edge_description(relationship, llm_manager)
