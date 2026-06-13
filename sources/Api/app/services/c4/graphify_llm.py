"""OpenRouter LLM client for C4 inference from Graphify graph summaries."""

import json
import logging
import os
import time
from typing import Any

from app.domain.exceptions import LLMConnectionError, LLMResponseError

logger = logging.getLogger(__name__)

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "minimax/minimax-m3"

_C4_PROMPT_TEMPLATE = """\
You are a software architect. Analyze the codebase knowledge graph summary below \
and produce a complete C4 architecture model (three levels) as a single JSON object.

## Knowledge Graph Summary
{graph_summary}

## Required JSON output schema

{{
  "system_context": {{
    "name": "<short system name>",
    "purpose": "<one sentence — what the system does>",
    "domain": "<business domain: fintech | devtools | ecommerce | healthcare | ai | data | platform | other>",
    "owner": "<team or person inferred from README/CODEOWNERS/git nodes>",
    "status": "<ACTIVE | MAINTENANCE | DEPRECATED | ARCHIVED>",
    "tier": "<Tier 1 | Tier 2 | Tier 3 | Unknown>",
    "data_class": "<PII | Credit-Card | Internal | Public | Unknown>",
    "compliance": "<LOW_RISK | MEDIUM_RISK | HIGH_RISK>",
    "actors": [{{"name": "...", "description": "...", "role": "..."}}],
    "external_dependencies": [{{"name": "...", "type": "...", "description": "..."}}],
    "languages": [{{"language": "..."}}],
    "frameworks": [{{"framework": "..."}}]
  }},
  "containers": [
    {{
      "name": "<container name>",
      "technology": "<main language or runtime>",
      "container_type": "<service | database | frontend | cache | queue | gateway | worker>",
      "protocol": "<HTTP | gRPC | AMQP | TCP | none>",
      "description": "<what this container does>",
      "is_infrastructure_only": <true if database/cache/queue, else false>
    }}
  ],
  "components": [
    {{
      "name": "<component name>",
      "type": "component",
      "component_type": "<http_handler | database_adapter | task_processor | \
event_listener | service_layer | utility | model>",
      "container": "<must match a container name from above>",
      "language": "<language>",
      "description": "<what this component does>",
      "endpoint_path": "<HTTP path or empty string>",
      "endpoint_method": "<GET | POST | PUT | DELETE | empty string>"
    }}
  ],
  "relationships": {{
    "context": [{{"source": "...", "destination": "...", "description": "..."}}],
    "containers": [{{"from": "...", "to": "...", "protocol": "...", "description": "..."}}],
    "components": [{{"from": "...", "to": "...", "label": "calls | imports | uses"}}]
  }}
}}

Rules:

CONTAINERS — deployment boundary rules (strict):
- A container is a separately deployable unit: a distinct OS process or independently runnable runtime that serves live traffic or processes jobs.
- Use `deployment_units` from the summary as the primary signal. Each entry with its own runtime manifest (package.json, Gemfile, go.mod, etc.) in a separate directory is a strong candidate — but apply the exclusions below before accepting it.
- Check `deployment_units.procfile` for explicit process names (e.g. "web", "worker", "streaming") — each named process is a container.
- Do NOT split code that runs inside the same process into multiple containers. E.g. if federation logic lives inside the Rails app process, it is a component of the Rails container, not a separate container.
- Infrastructure (databases, caches, queues) count as containers only when they are deployed alongside the app (not purely external SaaS).

NOT containers — exclude these even if they appear in deployment_units:
- Build tooling: directories named buildSrc, gradle, cmake, tools, scripts, hack, or any directory whose sole purpose is building/compiling other code (Gradle wrapper, Makefile-only dirs, CMakeLists.txt roots).
- Documentation sites: directories named docs, documentation, docusaurus, storybook, mkdocs, wiki, site — even if they have a package.json, they are publishing artifacts not runtime services.
- CI/CD config: .github, .circleci, .gitlab, Jenkinsfile, .drone — these describe pipelines, not deployable units.
- Infrastructure-as-code: directories named terraform, k8s, kubernetes, helm, charts, infra, deploy, pulumi — they describe containers but are not containers themselves.
- Test suites: directories named e2e, tests, test, spec, __tests__, cypress, playwright, fixtures — test runners are not runtime services.
- Shared libraries without a network boundary: a packages/shared, lib, sdk, or common directory that is imported by other containers but has no HTTP/RPC/queue entry point of its own is a component, not a container.

COMPONENTS — entry point rules (strict):
- Components are architectural entry points only: HTTP endpoint groups, background job classes, event/queue consumers, database adapters, public service facades.
- Do NOT include: internal utility classes, UI atoms (icon components, hooks, helpers), low-level data structures, or implementation details.
- Aim for 3–8 components per container. Prefer fewer, broader components over many fine-grained ones.
- Each component must justify its inclusion by being a clear boundary or integration point.

GENERAL:
- Derive containers primarily from `deployment_units`, secondarily from top community clusters.
- Derive components from god nodes that are entry points (controllers, workers, consumers, adapters).
- Derive external_dependencies from the external_imports list.
- Derive actors from doc_nodes that mention users, clients, or personas.
- Only output valid JSON — no markdown fences, no explanation, no trailing text.
"""


def build_c4_prompt(graph_summary: str) -> str:
    return _C4_PROMPT_TEMPLATE.format(graph_summary=graph_summary)


def call_openrouter(prompt: str) -> dict[str, Any]:
    """Send *prompt* to minimax/minimax-m3 via OpenRouter and return parsed JSON.

    Args:
        prompt: The full prompt string (graph summary + schema instructions).

    Returns:
        Parsed JSON dict from the model.

    Raises:
        LLMConnectionError: If the API call fails.
        LLMResponseError: If the response cannot be parsed as JSON.
    """
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMConnectionError("openai package is required for OpenRouter calls") from exc

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise LLMConnectionError("OPENROUTER_API_KEY is not set")

    model = os.environ.get("OPENROUTER_MODEL", _DEFAULT_MODEL)
    logger.info("Calling OpenRouter model=%s prompt_chars=%d", model, len(prompt))

    client = OpenAI(base_url=_OPENROUTER_BASE_URL, api_key=api_key)

    raw = ""
    for attempt in range(1, 4):  # up to 3 attempts
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=8192,
            )
        except Exception as exc:
            raise LLMConnectionError(f"OpenRouter request failed: {exc}") from exc

        msg = response.choices[0].message
        # minimax-m3 is a reasoning model: on some calls content is null
        # and the answer lands in the reasoning field instead.
        raw = msg.content or getattr(msg, "reasoning", None) or ""
        logger.info("OpenRouter attempt %d response: %d chars finish_reason=%s",
                    attempt, len(raw), getattr(response.choices[0], "finish_reason", "?"))

        if not raw.strip():
            logger.warning("OpenRouter returned empty content on attempt %d — retrying", attempt)
            if attempt < 3:
                time.sleep(5)
            continue

        # Strip markdown fences if the model wraps the JSON
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("```", 2)[-1] if stripped.count("```") >= 2 else stripped
            stripped = stripped.lstrip("json").lstrip("\n").rsplit("```", 1)[0].strip()

        try:
            # raw_decode stops at the first complete JSON object, ignoring trailing text
            obj, _ = json.JSONDecoder().raw_decode(stripped)
            return obj
        except json.JSONDecodeError as exc:
            logger.warning(
                "OpenRouter attempt %d returned invalid JSON (%s) — retrying", attempt, exc
            )
            if attempt < 3:
                time.sleep(5)

    raise LLMResponseError(f"OpenRouter returned invalid JSON after 3 attempts\nRaw: {raw[:500]}")
