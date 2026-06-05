"""Phase 0 LLM-driven container discovery from executable/structural signals.

Runs BEFORE structural detectors to seed the container list from signals that
actually reflect the running system — NOT documentation (README is excluded as
it goes stale and describes intent, not reality).

Reliable signals used:
  - docker-compose files (explicit runtime service definitions)
  - .env.example / .env.sample (real connection strings reveal what services exist)
  - CI/CD workflow files (docker build/push commands, service names)
  - Shell scripts containing docker run / docker-compose up commands
  - settings.gradle / pyproject.toml workspace members (build-time structure)

The LLM produces a "proposed_containers" list that gets primed into the
container registry before rule-based detection runs. Structural detectors
then validate and enrich each proposal; unconfirmed proposals remain with
detection_source="llm-proposed" for the enrichment phase to review.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from app.services.c4.containers.c4_types import coerce_container_type

logger = logging.getLogger(__name__)

_ENV_MAX_CHARS = 2000
_SCRIPT_MAX_CHARS = 1500
_COMPOSE_MAX_CHARS = 3000
_WORKFLOW_MAX_CHARS = 2000
_GRADLE_MAX_CHARS = 2000

# Shell patterns that indicate a script is actually running services
_DOCKER_RUN_PAT = re.compile(
    r"docker\s+(?:run|compose|stack)|docker-compose\s+up",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = """\
You are an expert software architect specialising in the C4 Model (Simon Brown).

TASK
Given executable/structural signals from a code repository, identify ALL
containers this system consists of in the C4 sense — a container is "an
application or data store that needs to be running for the system to work."

SIGNAL TYPES PROVIDED (all are reliable — they describe what actually runs):
  - docker_compose: explicit service definitions, images, ports, depends_on
  - env_example:    .env.example/.env.sample — connection strings reveal
                    real external services (DATABASE_URL=, REDIS_URL=, etc.)
  - ci_workflows:   GitHub Actions / CI — docker build targets and service names
  - shell_scripts:  scripts with `docker run` or `docker-compose up` commands
  - gradle_settings: Gradle subproject names (Java/Kotlin services)
  - ci_services:    services: blocks in CI config (databases, brokers spun up for tests)

Include:
  - Application services: APIs, web apps, workers, schedulers
  - Data stores: databases, caches, object storage
  - Message brokers: Kafka, RabbitMQ, etc.
  - Workflow engines: Temporal, Airflow, etc.
  - External services referenced by connection strings in env files

DO NOT include:
  - Build tools, linters, test fixtures, one-off migration jobs
  - Documentation sites
  - Sidecar / init containers
  - CI-only test helpers that don't run in production

For each container:
  - name: kebab-case identifier (e.g. "airbyte-server", "postgres")
  - container_type: exactly one of the following values (copy verbatim):
                    ServerSideWebApp | ClientSideWebApp | MobileApp |
                    ConsoleApp | ServerlessFunction | ShellScript |
                    Database | BlobStore | FileSystem | MessageBroker | Unknown
    Guidance:
      • Background workers, job runners (Sidekiq, Celery), schedulers → ConsoleApp
      • React/Vue/Angular SPAs, static frontends → ClientSideWebApp
      • Redis/Memcached used as cache or key-value store → Database
      • Redis/NATS used purely for Pub/Sub → MessageBroker
      • If the role is unclear → Unknown
  - technology: e.g. "Java/Kotlin", "Python/FastAPI", "PostgreSQL", "Temporal"
  - description: 1-sentence purpose
  - confidence: 0.0-1.0
  - source_signal: compose | env | ci | script | gradle

Return ONLY a JSON object — no markdown, no comments:
{
  "proposed_containers": [
    {
      "name": "...",
      "container_type": "...",
      "technology": "...",
      "description": "...",
      "confidence": 0.0,
      "source_signal": "..."
    }
  ]
}
"""


def collect_repo_signals(repo_path: Path) -> dict[str, Any]:
    """Collect executable/structural signals from the repository root.

    Deliberately excludes README — documentation goes stale and is unreliable
    for container discovery. Only signals that reflect the actual running system
    are included.
    """
    signals: dict[str, Any] = {
        "repo_name": repo_path.name,
        "top_level_dirs": [],
    }

    try:
        signals["top_level_dirs"] = [
            item.name for item in sorted(repo_path.iterdir())
            if item.is_dir() and not item.name.startswith(".")
        ]
    except OSError:
        pass

    # .env example files — connection strings are the most reliable signal
    for name in (".env.example", ".env.sample", ".env.template", ".env.dev", ".env.defaults"):
        env_file = repo_path / name
        if env_file.is_file():
            try:
                signals["env_example"] = env_file.read_text(
                    encoding="utf-8", errors="ignore"
                )[:_ENV_MAX_CHARS]
            except OSError:
                pass
            break

    # docker-compose files at root
    compose_contents: dict[str, str] = {}
    for pattern in (
        "docker-compose.yml", "docker-compose.yaml",
        "docker-compose.override.yml", "docker-compose.override.yaml",
        "compose.yml", "compose.yaml",
    ):
        compose_file = repo_path / pattern
        if compose_file.is_file():
            try:
                compose_contents[pattern] = compose_file.read_text(
                    encoding="utf-8", errors="ignore"
                )[:_COMPOSE_MAX_CHARS]
            except OSError:
                pass
    if compose_contents:
        signals["docker_compose"] = compose_contents

    # Shell scripts that actually run docker commands (not just mention services)
    shell_scripts: dict[str, str] = {}
    for sh_file in sorted(repo_path.glob("*.sh"))[:6]:
        try:
            content = sh_file.read_text(encoding="utf-8", errors="ignore")
            if _DOCKER_RUN_PAT.search(content):
                shell_scripts[sh_file.name] = content[:_SCRIPT_MAX_CHARS]
        except OSError:
            pass
    if shell_scripts:
        signals["shell_scripts"] = shell_scripts

    # CI/CD workflow files — docker build targets and services: blocks
    ci_workflows: dict[str, str] = {}
    workflow_dirs = [
        repo_path / ".github" / "workflows",
        repo_path / ".gitlab-ci.yml",
        repo_path / ".circleci",
    ]
    for wf_dir in workflow_dirs:
        if wf_dir.is_file():
            try:
                content = wf_dir.read_text(encoding="utf-8", errors="ignore")
                if "docker" in content.lower() or "services:" in content:
                    ci_workflows[wf_dir.name] = content[:_WORKFLOW_MAX_CHARS]
            except OSError:
                pass
        elif wf_dir.is_dir():
            for wf_file in sorted(wf_dir.glob("*.yml"))[:4]:
                try:
                    content = wf_file.read_text(encoding="utf-8", errors="ignore")
                    if "docker" in content.lower() or "services:" in content:
                        ci_workflows[wf_file.name] = content[:_WORKFLOW_MAX_CHARS]
                except OSError:
                    pass
    if ci_workflows:
        signals["ci_workflows"] = ci_workflows

    # Gradle settings — Java/Kotlin multi-project workspace members
    for name in ("settings.gradle", "settings.gradle.kts"):
        settings_file = repo_path / name
        if settings_file.is_file():
            try:
                signals["gradle_settings"] = settings_file.read_text(
                    encoding="utf-8", errors="ignore"
                )[:_GRADLE_MAX_CHARS]
            except OSError:
                pass
            break

    # pyproject.toml workspace (Python monorepos)
    pyproject = repo_path / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            if "workspace" in content or "members" in content:
                signals["pyproject_workspace"] = content[:_GRADLE_MAX_CHARS]
        except OSError:
            pass

    return signals


def build_discovery_prompt(signals: dict[str, Any]) -> str:
    """Build the LLM discovery prompt from collected signals."""
    sections = [
        _SYSTEM_PROMPT,
        "\n=== REPOSITORY SIGNALS ===",
        json.dumps(signals, indent=2),
        (
            "\nBased on the signals above, identify all containers this system has.\n"
            "/no_think\n"
            "CRITICAL: Return ONLY a JSON object. Start with { and end with }. "
            "No markdown, no explanation."
        ),
    ]
    return "\n".join(sections)


def _strip_thinking_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json_object(text: str) -> Optional[str]:
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


def parse_discovery_response(response_text: Optional[str]) -> list[dict[str, Any]]:
    """Parse LLM discovery response into a list of proposed container dicts."""
    if not response_text:
        return []

    cleaned = _strip_thinking_tags(response_text)
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned).strip()

    json_str = _extract_json_object(cleaned) or _extract_json_object(response_text)
    if not json_str:
        logger.debug("LLM discovery: could not extract JSON from response")
        return []

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.debug("LLM discovery: JSON parse error: %s", exc)
        return []

    if not isinstance(data, dict):
        return []

    proposed = data.get("proposed_containers", [])
    if not isinstance(proposed, list):
        return []

    return [item for item in proposed if isinstance(item, dict) and item.get("name")]


def discover_containers(
    repo_path: Path,
    llm_manager: Any,
) -> list[dict[str, Any]]:
    """Run Phase 0 LLM discovery and return proposed containers.

    Each returned container dict carries detection_source="llm-proposed"
    and is ready for priming into ContainerManager.containers before
    structural detectors run.

    Returns an empty list if the LLM is unavailable or no reliable signals exist.
    """
    if llm_manager is None:
        return []

    signals = collect_repo_signals(repo_path)

    # Only proceed if we have at least one reliable executable signal
    reliable_signals = ("env_example", "docker_compose", "shell_scripts",
                        "ci_workflows", "gradle_settings", "pyproject_workspace")
    if not any(k in signals for k in reliable_signals):
        logger.debug("LLM discovery: no reliable executable signals found, skipping")
        return []

    prompt = build_discovery_prompt(signals)

    found_signals = [k for k in reliable_signals if k in signals]
    logger.info("LLM discovery: scanning signals (%s)", ", ".join(found_signals))

    try:
        raw = llm_manager.generate_text(
            prompt,
            max_tokens=1024,
            temperature=0.1,
            use_cache=True,
        )
    except Exception as exc:
        logger.warning("LLM discovery call failed: %s", exc)
        return []

    proposed = parse_discovery_response(raw)
    logger.info("LLM discovery: proposed %d containers from executable signals", len(proposed))

    result: list[dict[str, Any]] = []
    for item in proposed:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        container: dict[str, Any] = {
            "c4_level": 2,
            "type": "container",
            "name": name,
            "container_type": coerce_container_type(item.get("container_type")),
            "technology": item.get("technology") or "Unknown",
            "protocol": "",
            "path": "",
            "description": item.get("description") or "",
            "detection_source": "llm-proposed",
            "llm_discovery_confidence": float(item.get("confidence", 0.5)),
            "llm_discovery_signal": item.get("source_signal", ""),
            "dependencies_internal": [],
            "relationships": [],
        }
        result.append(container)

    return result
