"""External dependency detection for C4 Context level."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

try:
    import tomllib as tomli
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli
import yaml

from app.utils.fs_utils import limited_rglob
from .decision_models import (
    DecisionMode,
    EvidenceItem,
    ExtractionDecision,
    ReviewItem,
    ReviewStatus,
)
from .dependency_classifier import (
    DependencyClassification,
    DependencyClassifier,
    DependencyType,
)
from .provider_catalog import (
    ProviderCatalogEntry,
    ProviderMatchResult,
    explain_provider_match_from_env_var,
    explain_provider_match_from_image,
    explain_provider_match_from_package,
    explain_provider_match_from_url,
    match_provider_from_env_var,
    match_provider_from_image,
    match_provider_from_package,
    match_provider_from_url,
)


# NuGet package prefix -> (external service label, dep type)
NUGET_DEPENDENCY_MAP: dict[str, tuple[str, str]] = {
    "Azure.Messaging.ServiceBus": ("Azure Service Bus", "messaging"),
    "Azure.Storage.Blobs": ("Azure Blob Storage", "storage"),
    "Azure.Storage.Queues": ("Azure Queue Storage", "messaging"),
    "Azure.Cosmos": ("Azure Cosmos DB", "database"),
    "Azure.Identity": ("Azure Identity", "authentication"),
    "Azure.Security.KeyVault": ("Azure Key Vault", "security"),
    "AWSSDK.S3": ("AWS S3", "storage"),
    "AWSSDK.SQS": ("AWS SQS", "messaging"),
    "AWSSDK.DynamoDBv2": ("AWS DynamoDB", "database"),
    "AWSSDK.SecretsManager": ("AWS Secrets Manager", "security"),
    "Confluent.Kafka": ("Kafka", "messaging"),
    "MassTransit": ("MassTransit (Messaging)", "messaging"),
    "RabbitMQ.Client": ("RabbitMQ", "messaging"),
    "MongoDB.Driver": ("MongoDB", "database"),
    "Npgsql": ("PostgreSQL", "database"),
    "MySql.Data": ("MySQL", "database"),
    "MySqlConnector": ("MySQL", "database"),
    "Microsoft.Data.SqlClient": ("SQL Server", "database"),
    "System.Data.SqlClient": ("SQL Server", "database"),
    "SendGrid": ("SendGrid (Email)", "email"),
    "Stripe.net": ("Stripe", "payment"),
    "Elastic.Clients.Elasticsearch": ("Elasticsearch", "search"),
    "NEST": ("Elasticsearch", "search"),
    "StackExchange.Redis": ("Redis", "cache"),
    "Twilio": ("Twilio", "sms"),
    "Sentry.AspNetCore": ("Sentry", "error-tracking"),
    "Datadog.Trace": ("Datadog", "monitoring"),
    "Grpc.Net.Client": ("gRPC", "rpc"),
    "Microsoft.EntityFrameworkCore.SqlServer": ("SQL Server", "database"),
    "Microsoft.EntityFrameworkCore.Npgsql": ("PostgreSQL", "database"),
    "Microsoft.EntityFrameworkCore.Cosmos": ("Azure Cosmos DB", "database"),
    "Pomelo.EntityFrameworkCore.MySql": ("MySQL", "database"),
    "AspNetCore.HealthChecks.SqlServer": ("SQL Server", "database"),
    "AspNetCore.HealthChecks.Redis": ("Redis", "cache"),
    "AspNetCore.HealthChecks.Kafka": ("Kafka", "messaging"),
    "Microsoft.AspNetCore.SignalR.StackExchangeRedis": ("Redis", "cache"),
    "Serilog": ("Serilog (Logging)", "logging"),
    "OpenTelemetry": ("OpenTelemetry", "observability"),
    "Consul": ("Consul", "service-discovery"),
}

NON_SERVICE_HOSTS = {
    "shields.io",
    "website-files.com",
    "docusaurus.com",
    "youtube.com",
    "youtu.be",
    "github.com",
    "github.io",
    "readme.io",
    "marketing.com",
    "dtdg.co",
    "cdn.jsdelivr.net",
    "cdn.tailnet",
    "netlify.app",
}

GENERIC_URL_PATTERN = r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"')\];,}<>]+"
REVIEW_THRESHOLD = 0.70
CONTEXT_NAME_SUFFIXES: tuple[tuple[str, str], ...] = (
    (" gateway api", "Gateway API"),
    (" rest api", "REST API"),
    (" api", "API"),
    (" sdk", "SDK"),
    (" client", "Client"),
    (" endpoint", "Endpoint"),
    (" webhook", "Webhook"),
)

logger = logging.getLogger(__name__)


class DependencyDetector:
    """Detects external dependencies for C4 Context."""

    def __init__(self, repo_path: Path, llm_manager=None, enable_classification: bool = True):
        """Initialize dependency detector."""
        self.repo_path = Path(repo_path).resolve()
        self.llm_manager = llm_manager
        self.classifier = DependencyClassifier(llm_manager) if enable_classification else None
        self.last_review_items: list[dict[str, Any]] = []
        self._repo_domain: str | None = None

    def _get_repo_domain(self) -> str | None:
        """Lazily extract domain from git remote origin."""
        if self._repo_domain is not None:
            return self._repo_domain
        try:
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None
            remote_url = result.stdout.strip()
            if not remote_url:
                return None
            if remote_url.startswith("git@"):
                remote_url = remote_url.replace("git@", "https://").replace(".com:", ".com/")
            remote_url = remote_url.rstrip(".git")
            parsed = urlparse(remote_url)
            self._repo_domain = parsed.hostname or None
            return self._repo_domain
        except (subprocess.SubprocessError, OSError):
            return None

    def detect_external_dependencies(self) -> list[dict[str, Any]]:
        """Detect external service dependencies and annotate them with decision metadata."""
        raw_deps = (
            self._parse_dependency_files()
            + self._parse_requirements_dependencies()
            + self._parse_helm_values()
            + self._parse_env_files()
            + self._parse_appsettings_files()
            + self._parse_deployment_files()
            + self._parse_readme_dependencies()
            + self._parse_nuget_dependencies()
        )

        enriched = [self._enrich_dependency(dep) for dep in raw_deps]
        merged = self._merge_dependencies(enriched)
        self.last_review_items = [
            dep["review_item"] for dep in merged if dep.get("review_item")
        ]
        return merged

    def detect_deployment_dependencies(self) -> list[dict[str, Any]]:
        """Return dependency signals discovered from deployment-oriented files."""
        raw_deps = (
            self._parse_helm_values()
            + self._parse_appsettings_files()
            + self._parse_deployment_files()
        )
        return self._merge_dependencies([self._enrich_dependency(dep) for dep in raw_deps])

    def get_last_review_items(self) -> list[dict[str, Any]]:
        """Return review items emitted by the most recent detection run."""
        return list(self.last_review_items)

    def detect_dependency_freshness_alerts(self) -> list[dict[str, Any]]:
        """Detect dependencies with unpinned or non-semver versions."""
        alerts: list[dict[str, Any]] = []
        alerts.extend(self._scan_requirements_files())
        alerts.extend(self._scan_pyproject_versions())
        alerts.extend(self._scan_package_json_versions())

        seen = set()
        deduped: list[dict[str, Any]] = []
        for alert in alerts:
            key = (alert.get("dependency"), alert.get("issue"), alert.get("source"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(alert)

        return deduped

    def _external_dependency_patterns(self) -> dict[str, tuple[str, str]]:
        """Return broad fallback patterns for dependencies not yet in the provider catalog."""
        return {
            "stripe": ("Stripe", "payment"),
            "aws": ("AWS", "cloud"),
            "s3": ("AWS S3", "storage"),
            "postgres": ("PostgreSQL", "database"),
            "postgresql": ("PostgreSQL", "database"),
            "mysql": ("MySQL", "database"),
            "mariadb": ("MariaDB", "database"),
            "mongodb": ("MongoDB", "database"),
            "redis": ("Redis", "cache"),
            "kafka": ("Kafka", "messaging"),
            "rabbitmq": ("RabbitMQ", "messaging"),
            "elasticsearch": ("Elasticsearch", "search"),
            "opensearch": ("OpenSearch", "search"),
            "auth0": ("Auth0", "authentication"),
            "okta": ("Okta", "authentication"),
            "sendgrid": ("SendGrid", "email"),
            "twilio": ("Twilio", "sms"),
            "slack": ("Slack", "notifications"),
            "datadog": ("Datadog", "monitoring"),
            "sentry": ("Sentry", "error-tracking"),
            "openai": ("OpenAI", "ai"),
            "anthropic": ("Anthropic", "ai"),
        }

    def _make_dependency(
        self,
        *,
        name: str,
        dep_type: str,
        detected_from: str,
        context: str = "",
        url: str = "",
        package_name: str = "",
        env_var: str = "",
        image: str = "",
        evidence_type: str = "detected_reference",
    ) -> dict[str, Any]:
        dep = {
            "name": name,
            "type": dep_type,
            "detected_from": detected_from,
            "context": context,
            "evidence_type": evidence_type,
        }
        if url:
            dep["url"] = url
        if package_name:
            dep["package_name"] = package_name
        if env_var:
            dep["env_var"] = env_var
        if image:
            dep["image"] = image
        return dep

    def _parse_dependency_files(self) -> list[dict[str, Any]]:
        """Parse package manifests for external dependencies."""
        deps: list[dict[str, Any]] = []
        external_patterns = self._external_dependency_patterns()

        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject, "rb") as f:
                    data = tomli.load(f)
                project_deps = data.get("project", {}).get("dependencies", []) or []
                poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {}) or {}

                for dep_spec in project_deps:
                    dep_name, _ = self._split_dependency_spec(dep_spec)
                    if not dep_name:
                        continue
                    deps.extend(
                        self._build_package_dependency_candidates(
                            dep_name, "pyproject.toml", external_patterns
                        )
                    )

                for dep_name in poetry_deps:
                    if str(dep_name).lower() == "python":
                        continue
                    deps.extend(
                        self._build_package_dependency_candidates(
                            str(dep_name), "pyproject.toml", external_patterns
                        )
                    )
            except (OSError, ValueError) as e:
                logger.debug("Error parsing pyproject.toml: %s", e)

        for package_json in limited_rglob(self.repo_path, "package.json"):
            try:
                with open(package_json) as f:
                    data = json.load(f)
                all_deps = {
                    **(data.get("dependencies", {}) or {}),
                    **(data.get("devDependencies", {}) or {}),
                }
                for dep_name in all_deps:
                    deps.extend(
                        self._build_package_dependency_candidates(
                            str(dep_name),
                            str(package_json.relative_to(self.repo_path)),
                            external_patterns,
                        )
                    )
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.debug("Error parsing package.json: %s", e)

        return deps

    def _build_package_dependency_candidates(
        self,
        package_name: str,
        detected_from: str,
        fallback_patterns: dict[str, tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """Build dependency candidates from a package reference."""
        candidates: list[dict[str, Any]] = []
        catalog_entry = match_provider_from_package(package_name)
        if catalog_entry:
            candidates.append(
                self._make_dependency(
                    name=catalog_entry.provider,
                    dep_type=catalog_entry.category,
                    detected_from=detected_from,
                    context=f"Dependency: {package_name}",
                    package_name=package_name,
                    evidence_type="package_reference",
                )
            )
            return candidates

        package_lower = package_name.lower()
        for pattern, (name, dep_type) in fallback_patterns.items():
            if pattern in package_lower:
                candidates.append(
                    self._make_dependency(
                        name=name,
                        dep_type=dep_type,
                        detected_from=detected_from,
                        context=f"Dependency: {package_name}",
                        package_name=package_name,
                        evidence_type="package_reference",
                    )
                )
                break

        return candidates

    def _parse_requirements_dependencies(self) -> list[dict[str, Any]]:
        """Parse requirements files for external package references."""
        deps: list[dict[str, Any]] = []
        external_patterns = self._external_dependency_patterns()
        for req_file in limited_rglob(self.repo_path, "requirements*.txt"):
            try:
                lines = req_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for line in lines:
                raw = line.split("#", 1)[0].strip()
                if not raw or raw.startswith("-"):
                    continue
                dep_name, _ = self._split_dependency_spec(raw)
                if not dep_name:
                    dep_name = re.split(r"\s+", raw, 1)[0]
                deps.extend(
                    self._build_package_dependency_candidates(
                        dep_name,
                        str(req_file.relative_to(self.repo_path)),
                        external_patterns,
                    )
                )
        return deps

    def _parse_nuget_dependencies(self) -> list[dict[str, Any]]:
        """Scan .csproj files for NuGet packages and map them to external services."""
        deps: list[dict[str, Any]] = []
        for csproj in limited_rglob(self.repo_path, "*.csproj"):
            if not csproj.is_file():
                continue
            rel_path = str(csproj.relative_to(self.repo_path))
            try:
                tree = ET.parse(str(csproj))
                root = tree.getroot()
                for ref in root.findall(".//PackageReference"):
                    pkg = ref.get("Include", "")
                    if not pkg:
                        continue
                    catalog_entry = match_provider_from_package(pkg)
                    if catalog_entry:
                        deps.append(
                            self._make_dependency(
                                name=catalog_entry.provider,
                                dep_type=catalog_entry.category,
                                detected_from=rel_path,
                                context=f"NuGet package: {pkg}",
                                package_name=pkg,
                                evidence_type="package_reference",
                            )
                        )
                        continue
                    for prefix, (service_name, dep_type) in NUGET_DEPENDENCY_MAP.items():
                        if pkg.lower().startswith(prefix.lower()):
                            deps.append(
                                self._make_dependency(
                                    name=service_name,
                                    dep_type=dep_type,
                                    detected_from=rel_path,
                                    context=f"NuGet package: {pkg}",
                                    package_name=pkg,
                                    evidence_type="package_reference",
                                )
                            )
                            break
            except ET.ParseError as e:
                logger.debug("Could not parse %s: %s", csproj, e)

        return deps

    def _parse_readme_dependencies(self) -> list[dict[str, Any]]:
        """Parse README/docs for external service references."""
        deps: list[dict[str, Any]] = []
        external_patterns = self._external_dependency_patterns()

        candidate_files: list[Path] = []
        for name in ["README.md", "README.rst", "README.txt"]:
            path = self.repo_path / name
            if path.exists():
                candidate_files.append(path)

        candidate_files.extend(list(limited_rglob(self.repo_path, "docs/*.md")))
        candidate_files.extend(list(limited_rglob(self.repo_path, "documentation/*.md")))

        for doc in candidate_files:
            try:
                content = doc.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            lowered = content.lower()
            rel_path = str(doc.relative_to(self.repo_path))
            for pattern, (name, dep_type) in external_patterns.items():
                if pattern in lowered:
                    deps.append(
                        self._make_dependency(
                            name=name,
                            dep_type=dep_type,
                            detected_from=rel_path,
                            context=f"Pattern match: {pattern}",
                            evidence_type="documentation_reference",
                        )
                    )

            for url in re.findall(GENERIC_URL_PATTERN, content):
                provider = match_provider_from_url(url)
                name = provider.provider if provider else self._extract_service_name_from_url(url)
                if name is None:
                    continue
                deps.append(
                    self._make_dependency(
                        name=name,
                        dep_type=provider.category if provider else "external_service",
                        detected_from=rel_path,
                        context=url,
                        url=url,
                        evidence_type="documentation_reference",
                    )
                )

        return deps

    def _parse_deployment_files(self) -> list[dict[str, Any]]:
        """Parse deployment files for service references."""
        deps: list[dict[str, Any]] = []
        external_patterns = self._external_dependency_patterns()

        for dockerfile in limited_rglob(self.repo_path, "Dockerfile"):
            try:
                content = dockerfile.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel_path = str(dockerfile.relative_to(self.repo_path))
            for pattern, (name, dep_type) in external_patterns.items():
                if pattern in content.lower():
                    deps.append(
                        self._make_dependency(
                            name=name,
                            dep_type=dep_type,
                            detected_from=rel_path,
                            context=f"Pattern match: {pattern}",
                            evidence_type="deployment_reference",
                        )
                    )
            for url in re.findall(GENERIC_URL_PATTERN, content):
                provider = match_provider_from_url(url)
                name = provider.provider if provider else self._extract_service_name_from_url(url)
                if name is None:
                    continue
                deps.append(
                    self._make_dependency(
                        name=name,
                        dep_type=provider.category if provider else "external_service",
                        detected_from=rel_path,
                        context=url,
                        url=url,
                        evidence_type="deployment_reference",
                    )
                )

        for compose_file in limited_rglob(self.repo_path, "docker-compose*.y*ml"):
            try:
                data = yaml.safe_load(compose_file.read_text(encoding="utf-8", errors="ignore"))
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(data, dict):
                continue
            rel_path = str(compose_file.relative_to(self.repo_path))
            services = data.get("services", {}) or {}
            for service in services.values():
                if not isinstance(service, dict):
                    continue
                image = service.get("image")
                if isinstance(image, str):
                    provider = match_provider_from_image(image)
                    if provider:
                        deps.append(
                            self._make_dependency(
                                name=provider.provider,
                                dep_type=provider.category,
                                detected_from=rel_path,
                                context=image,
                                image=image,
                                evidence_type="deployment_reference",
                            )
                        )
                    else:
                        for pattern, (name, dep_type) in external_patterns.items():
                            if pattern in image.lower():
                                deps.append(
                                    self._make_dependency(
                                        name=name,
                                        dep_type=dep_type,
                                        detected_from=rel_path,
                                        context=image,
                                        image=image,
                                        evidence_type="deployment_reference",
                                    )
                                )
                                break

        return deps

    def _parse_helm_values(self) -> list[dict[str, Any]]:
        """Extract service references from Helm values."""
        deps: list[dict[str, Any]] = []
        for values_file in limited_rglob(self.repo_path, "values.yaml"):
            try:
                data = yaml.safe_load(values_file.read_text(encoding="utf-8", errors="ignore"))
            except (OSError, yaml.YAMLError):
                continue
            if not data:
                continue
            rel_path = str(values_file.relative_to(self.repo_path))
            for url in self._find_external_urls(data):
                provider = match_provider_from_url(url)
                name = provider.provider if provider else self._extract_service_name_from_url(url)
                if name is None:
                    continue
                deps.append(
                    self._make_dependency(
                        name=name,
                        dep_type=provider.category if provider else "external_service",
                        detected_from=rel_path,
                        context=url,
                        url=url,
                        evidence_type="config_reference",
                    )
                )

        return deps

    def _parse_env_files(self) -> list[dict[str, Any]]:
        """Parse .env files for provider hints and service references."""
        deps: list[dict[str, Any]] = []
        env_files = list(self.repo_path.glob("*.env")) + list(self.repo_path.glob(".env*"))

        for env_file in env_files:
            try:
                content = env_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for line in content.splitlines():
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, value = raw.split("=", 1)
                env_key = key.strip()
                env_value = value.strip().strip('"').strip("'")

                provider = match_provider_from_env_var(env_key)
                if provider:
                    deps.append(
                        self._make_dependency(
                            name=provider.provider,
                            dep_type=provider.category,
                            detected_from=env_file.name,
                            context=f"{env_key}={env_value[:120]}",
                            env_var=env_key,
                            evidence_type="env_reference",
                        )
                    )

                for url in re.findall(GENERIC_URL_PATTERN, env_value):
                    url_provider = match_provider_from_url(url)
                    name = url_provider.provider if url_provider else self._extract_service_name_from_url(url)
                    if name is None:
                        continue
                    deps.append(
                        self._make_dependency(
                            name=name,
                            dep_type=url_provider.category if url_provider else "external_service",
                            detected_from=env_file.name,
                            context=f"{env_key}={url}",
                            url=url,
                            env_var=env_key,
                            evidence_type="env_reference",
                        )
                    )

        return deps

    def _parse_appsettings_files(self) -> list[dict[str, Any]]:
        """Parse appsettings JSON files for dependency URLs and provider hints."""
        deps: list[dict[str, Any]] = []
        for appsettings in limited_rglob(self.repo_path, "appsettings*.json"):
            try:
                data = json.loads(appsettings.read_text(encoding="utf-8", errors="ignore"))
            except (OSError, json.JSONDecodeError, ValueError):
                continue

            rel_path = str(appsettings.relative_to(self.repo_path))
            for key_path, value in self._iter_scalar_values(data):
                if not isinstance(value, str):
                    continue
                env_provider = match_provider_from_env_var(key_path.split(".")[-1].upper())
                if env_provider:
                    deps.append(
                        self._make_dependency(
                            name=env_provider.provider,
                            dep_type=env_provider.category,
                            detected_from=rel_path,
                            context=f"{key_path}={value[:120]}",
                            evidence_type="config_reference",
                        )
                    )
                for url in re.findall(GENERIC_URL_PATTERN, value):
                    provider = match_provider_from_url(url)
                    name = provider.provider if provider else self._extract_service_name_from_url(url)
                    if name is None:
                        continue
                    deps.append(
                        self._make_dependency(
                            name=name,
                            dep_type=provider.category if provider else "external_service",
                            detected_from=rel_path,
                            context=f"{key_path}={url}",
                            url=url,
                            evidence_type="config_reference",
                        )
                    )

        return deps

    def _iter_scalar_values(self, data: Any, prefix: str = "") -> list[tuple[str, Any]]:
        """Flatten nested dictionaries into key/value paths."""
        values: list[tuple[str, Any]] = []
        if isinstance(data, dict):
            for key, value in data.items():
                next_prefix = f"{prefix}.{key}" if prefix else str(key)
                values.extend(self._iter_scalar_values(value, next_prefix))
        elif isinstance(data, list):
            for idx, value in enumerate(data):
                values.extend(self._iter_scalar_values(value, f"{prefix}[{idx}]"))
        else:
            values.append((prefix or "value", data))
        return values

    def _enrich_dependency(self, dep: dict[str, Any]) -> dict[str, Any]:
        """Attach provider metadata, decision details, and review state."""
        provider_match = self._resolve_catalog_match(dep)
        provider_entry = provider_match.entry if provider_match else None
        final_name = provider_entry.provider if provider_entry else dep.get("name", "Unknown")
        final_type = provider_entry.category if provider_entry else dep.get("type", "external_service")
        context_name, integration_surface = self._derive_context_identity(final_name)

        if provider_entry:
            classification = DependencyClassification(
                type=DependencyType(provider_entry.default_boundary),
                confidence=0.98,
                reasoning=f"Matched provider catalog entry for {provider_entry.provider}",
                decision_mode="deterministic",
                detection_source="provider_catalog",
            )
        elif self.classifier:
            classification = self.classifier.classify_dependency(
                name=final_name,
                dep_type=final_type,
                detected_from=dep.get("detected_from", ""),
                context=dep.get("context", ""),
            )
        else:
            classification = DependencyClassification(
                type=DependencyType.UNKNOWN,
                confidence=0.5,
                reasoning=f"No deterministic provider catalog match for '{final_name}'",
                decision_mode="deterministic",
                detection_source="raw_detection",
            )

        evidence = [
            EvidenceItem(
                type=dep.get("evidence_type", "detected_reference"),
                source=dep.get("detected_from", "unknown"),
                snippet=dep.get("context")
                or dep.get("url")
                or dep.get("package_name")
                or dep.get("env_var")
                or dep.get("image")
                or final_name,
            )
        ]

        internal_hint = self._infer_internal_hint(dep)
        needs_review = classification.type == DependencyType.UNKNOWN or classification.confidence < REVIEW_THRESHOLD
        review_reason = classification.reasoning

        if internal_hint and classification.type != DependencyType.TECHNICAL_INFRA:
            needs_review = True
            review_reason = internal_hint

        review_status = ReviewStatus.NEEDS_REVIEW if needs_review else ReviewStatus.AUTO_ACCEPTED
        decision = ExtractionDecision(
            value=final_name,
            confidence=classification.confidence,
            detection_source=classification.detection_source,
            decision_mode=DecisionMode(classification.decision_mode),
            review_status=review_status,
            evidence=evidence,
            metadata={
                "provider": provider_entry.provider if provider_entry else final_name,
                "company": provider_entry.company if provider_entry else None,
                "category": provider_entry.category if provider_entry else final_type,
                "boundary": classification.type.value,
                "catalog_match": provider_match.to_metadata() if provider_match else None,
            },
        )

        review_item = None
        if needs_review:
            review_item = ReviewItem(
                field="external_dependencies",
                candidate_value=final_name,
                confidence=classification.confidence,
                reason=review_reason,
                repo_path=str(self.repo_path),
                evidence=evidence,
            ).to_dict()

        enriched = {
            **dep,
            "name": final_name,
            "context_name": context_name,
            "integration_surface": integration_surface,
            "provider": provider_entry.provider if provider_entry else final_name,
            "company": provider_entry.company if provider_entry else None,
            "category": provider_entry.category if provider_entry else final_type,
            "dependency_type": classification.type.value,
            "classification_confidence": classification.confidence,
            "classification_reasoning": classification.reasoning,
            "decision_mode": classification.decision_mode,
            "decision": decision.to_dict(),
            "confidence": decision.confidence,
            "detection_source": decision.detection_source,
            "review_status": decision.review_status.value,
            "requires_human_review": needs_review,
            "review_threshold": REVIEW_THRESHOLD,
            "evidence": [item.to_dict() for item in evidence],
        }
        if review_item:
            enriched["review_item"] = review_item
        if needs_review:
            enriched["review_options"] = self._build_review_options(context_name)
            enriched["suggested_prompts"] = self._build_review_prompts(
                context_name, final_type, dep,
            )
        if internal_hint:
            enriched["internal_hint"] = internal_hint
        return enriched

    def _derive_context_identity(self, name: str) -> tuple[str, str | None]:
        """Return a business-facing context label and the stripped technical surface."""
        label = str(name or "").strip()
        if not label:
            return "External Service", None

        technical_surface: list[str] = []
        paren_match = re.search(r"\(([^)]+)\)\s*$", label)
        if paren_match:
            technical_surface.append(paren_match.group(1).strip())
            label = re.sub(r"\s*\([^)]+\)\s*$", "", label).strip()

        lowered = label.lower()
        for suffix, surface in CONTEXT_NAME_SUFFIXES:
            if lowered.endswith(suffix):
                label = label[: -len(suffix)].strip(" -")
                technical_surface.append(surface)
                break

        normalized_label = label or str(name or "").strip() or "External Service"
        surface = ", ".join(
            part for idx, part in enumerate(technical_surface) if part and part not in technical_surface[:idx]
        ) or None
        return normalized_label, surface

    def _build_review_options(self, context_name: str) -> list[dict[str, str]]:
        """Return user-facing review choices for ambiguous dependencies."""
        return [
            {
                "id": "context-business-system",
                "label": "Keep At Context Level",
                "value": "BUSINESS_SYSTEM",
                "description": (
                    f"Treat {context_name} as an external business company or SaaS "
                    "that belongs in the system context."
                ),
            },
            {
                "id": "container-technical-infra",
                "label": "Move To Container Level",
                "value": "TECHNICAL_INFRA",
                "description": (
                    f"Treat {context_name} as technical infrastructure or an "
                    "implementation detail that should not stay in the context diagram."
                ),
            },
        ]

    def _build_review_prompts(
        self, context_name: str, dep_type: str, dep: dict[str, Any]
    ) -> list[str]:
        """Generate context-specific prompt starters for ambiguous dependencies.

        Uses LLM if available to generate tailored prompts based on actual
        dependency evidence (source file, URL, classification confidence).
        Falls back to static prompts using actual dep evidence if LLM unavailable.
        """
        evidence = dep.get("context") or dep.get("url") or dep.get("name") or "unknown source"
        confidence = dep.get("classification_confidence", 0.5)
        review_threshold = dep.get("review_threshold", 0.7)
        prompt = (
            f"A C4 architecture dependency was detected:\n"
            f"- Name: {context_name}\n"
            f"- Type: {dep_type}\n"
            f"- Evidence: {evidence}\n"
            f"- Classification confidence: {confidence:.0%} "
            f"(below {review_threshold:.0%} threshold)\n\n"
            f"Generate exactly 2 short prompt starters (25 words or fewer each) "
            f"to help a human decide:\n"
            f"1. Whether this belongs at Context level (external business actor/SaaS) "
            f"or Container level (technical infra)\n"
            f"2. What specific architectural role this dependency likely plays\n"
            f'Return ONLY a JSON array of strings, no markdown: ["prompt1", "prompt2"]'
        )
        try:
            if self.llm_manager:
                response = self.llm_manager.generate_text(
                    prompt, max_tokens=200, temperature=0.3
                )
                text = response.strip()
                # Strip markdown code fences
                text = text.removeprefix("```json").strip().removeprefix("```").strip()
                # Find first JSON array [...] in response
                match = re.search(r'\[[\s\S]*\]', text)
                if match:
                    parsed = json.loads(match.group())
                    if isinstance(parsed, list) and len(parsed) >= 2:
                        return parsed[:2]
        except Exception:
            pass
        # Fallback: static prompts using actual evidence
        return [
            f"Is {context_name} ({dep_type}) a business actor or technical detail "
            f"given confidence {confidence:.0%} (threshold {review_threshold:.0%})?",
            f"What role does {context_name} play given it was found in: {evidence[:80]}?",
        ]

    def _resolve_catalog_match(self, dep: dict[str, Any]) -> ProviderMatchResult | None:
        """Resolve a provider catalog match from the richest available signal."""
        for package_name in (dep.get("package_name"), self._package_name_from_context(dep.get("context", ""))):
            if package_name:
                match = explain_provider_match_from_package(str(package_name))
                if match:
                    return match
        if dep.get("env_var"):
            match = explain_provider_match_from_env_var(str(dep["env_var"]))
            if match:
                return match
        if dep.get("url"):
            match = explain_provider_match_from_url(str(dep["url"]))
            if match:
                return match
        if dep.get("image"):
            match = explain_provider_match_from_image(str(dep["image"]))
            if match:
                return match
        return explain_provider_match_from_package(dep.get("name", ""))

    def _package_name_from_context(self, context: str) -> str | None:
        """Extract a package name from detector context strings."""
        if not context:
            return None
        if ":" not in context:
            return None
        _, raw = context.split(":", 1)
        candidate = raw.strip()
        return candidate or None

    def _infer_internal_hint(self, dep: dict[str, Any]) -> str | None:
        """Return a reason when a reference looks internal rather than external."""
        url = dep.get("url", "")
        if not url:
            return None
        try:
            parsed = urlparse(url)
        except ValueError:
            return None
        host = (parsed.hostname or "").lower()
        if not host:
            return None
        if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
            return f"URL host '{host}' is a local/internal address"
        if host.endswith(".internal") or ".internal." in host:
            return f"URL host '{host}' looks internal"
        if host.endswith(".svc.cluster.local"):
            return f"URL host '{host}' looks like a cluster-local service"
        if "." not in host:
            return f"URL host '{host}' looks like an internal container or service name"
        return None

    def _merge_dependencies(self, deps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merge duplicate provider detections while preserving evidence."""
        merged: dict[str, dict[str, Any]] = {}
        for dep in deps:
            key = dep.get("name", "").strip().lower()
            if not key:
                continue
            if key not in merged:
                merged[key] = {
                    **dep,
                    "detected_from_all": [dep.get("detected_from", "")],
                }
                continue

            existing = merged[key]
            existing["detected_from_all"] = sorted(
                {
                    *existing.get("detected_from_all", []),
                    dep.get("detected_from", ""),
                }
            )
            existing["evidence"] = self._merge_evidence(existing.get("evidence", []), dep.get("evidence", []))
            existing["decision"]["evidence"] = existing["evidence"]

            if dep.get("classification_confidence", 0.0) > existing.get("classification_confidence", 0.0):
                for field in (
                    "dependency_type",
                    "classification_confidence",
                    "classification_reasoning",
                    "decision_mode",
                    "confidence",
                    "detection_source",
                    "internal_hint",
                ):
                    if field in dep:
                        existing[field] = dep[field]
                existing["decision"]["confidence"] = dep.get("confidence", existing["decision"]["confidence"])
                existing["decision"]["detection_source"] = dep.get(
                    "detection_source", existing["decision"]["detection_source"]
                )
                existing["decision"]["decision_mode"] = dep.get(
                    "decision_mode", existing["decision"]["decision_mode"]
                )
                existing["decision"]["metadata"] = dep["decision"].get(
                    "metadata", existing["decision"].get("metadata", {})
                )

            if dep.get("review_status") == ReviewStatus.NEEDS_REVIEW.value:
                existing["review_status"] = ReviewStatus.NEEDS_REVIEW.value
                existing["decision"]["review_status"] = ReviewStatus.NEEDS_REVIEW.value
                if dep.get("review_item"):
                    existing["review_item"] = dep["review_item"]

            if not existing.get("company") and dep.get("company"):
                existing["company"] = dep["company"]

        return list(merged.values())

    def _merge_evidence(
        self,
        existing: list[dict[str, Any]],
        additional: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Deduplicate evidence items across repeated detections."""
        merged: list[dict[str, Any]] = []
        seen = set()
        for item in existing + additional:
            key = (item.get("type"), item.get("source"), item.get("snippet"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged

    def _scan_requirements_files(self) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        for req_file in limited_rglob(self.repo_path, "requirements*.txt"):
            try:
                lines = req_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue
            for line in lines:
                raw = line.split("#", 1)[0].strip()
                if not raw or raw.startswith("-"):
                    continue
                raw = raw.split(";", 1)[0].strip()
                if not raw:
                    continue
                match = re.match(r"^([A-Za-z0-9_.-]+)\s*([<>=!~]{1,2})\s*([^\s]+)$", raw)
                if match:
                    name, op, version = match.groups()
                    if op != "==" or "*" in version or "x" in version.lower():
                        alerts.append(
                            {
                                "dependency": name,
                                "version": version,
                                "issue": "range_version",
                                "source": str(req_file.relative_to(self.repo_path)),
                            }
                        )
                else:
                    pkg = re.split(r"\s+", raw, 1)[0]
                    issue = self._classify_version(raw)
                    if issue:
                        alerts.append(
                            {
                                "dependency": pkg,
                                "version": raw,
                                "issue": issue,
                                "source": str(req_file.relative_to(self.repo_path)),
                            }
                        )
        return alerts

    def _scan_pyproject_versions(self) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        pyproject = self.repo_path / "pyproject.toml"
        if not pyproject.exists():
            return alerts

        try:
            with open(pyproject, "rb") as f:
                data = tomli.load(f)
        except (OSError, ValueError):
            return alerts

        for dep in data.get("project", {}).get("dependencies", []) or []:
            name, version = self._split_dependency_spec(dep)
            issue = self._classify_version(version)
            if name and issue:
                alerts.append(
                    {
                        "dependency": name,
                        "version": version,
                        "issue": issue,
                        "source": "pyproject.toml",
                    }
                )

        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {}) or {}
        for name, spec in poetry_deps.items():
            if name.lower() == "python":
                continue
            version = ""
            if isinstance(spec, dict):
                version = str(spec.get("version", ""))
            elif spec is not None:
                version = str(spec)
            issue = self._classify_version(version)
            if issue:
                alerts.append(
                    {
                        "dependency": name,
                        "version": version,
                        "issue": issue,
                        "source": "pyproject.toml",
                    }
                )

        return alerts

    def _scan_package_json_versions(self) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        package_json = self.repo_path / "package.json"
        if not package_json.exists():
            return alerts

        try:
            with open(package_json) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            return alerts

        for section in ("dependencies", "devDependencies"):
            deps = data.get(section, {}) or {}
            if not isinstance(deps, dict):
                continue
            for name, version in deps.items():
                version_str = str(version)
                issue = self._classify_version(version_str)
                if issue:
                    alerts.append(
                        {
                            "dependency": name,
                            "version": version_str,
                            "issue": issue,
                            "source": f"package.json:{section}",
                        }
                    )

        return alerts

    def _classify_version(self, version: Optional[str]) -> Optional[str]:
        if version is None:
            return "unbounded_version"
        normalized = str(version).strip()
        if not normalized:
            return "unbounded_version"
        lowered = normalized.lower()
        if lowered in {"*", "latest"}:
            return "unbounded_version"
        if lowered.startswith(("git+", "http:", "https:", "file:", "workspace:", "path:")):
            return "non_semver_reference"
        if any(token in lowered for token in ("^", "~", ">", "<")):
            return "range_version"
        if "x" in lowered or "*" in lowered:
            return "range_version"
        return None

    def _split_dependency_spec(self, dep: str) -> tuple[Optional[str], Optional[str]]:
        if not dep:
            return None, None
        raw = str(dep).strip()
        if not raw:
            return None, None
        parts = re.split(r"[<>=!~]", raw, maxsplit=1)
        name = parts[0].strip() if parts else None
        if not name:
            return None, None
        match = re.match(r"^([A-Za-z0-9_.@/-]+)\s*([<>=!~]{1,2})\s*([^\s]+)$", raw)
        if match:
            _, op, version = match.groups()
            if op == "==":
                return name, version
            return name, raw
        return name, raw

    def _find_external_urls(self, data: dict, path: str = "") -> list[str]:
        """Recursively find URLs in nested dictionaries."""
        urls: list[str] = []
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    urls.extend(re.findall(GENERIC_URL_PATTERN, value))
                else:
                    urls.extend(self._find_external_urls(value, f"{path}.{key}"))
        elif isinstance(data, list):
            for item in data:
                urls.extend(self._find_external_urls(item, path))
        return urls

    def _extract_service_name_from_url(self, url: str) -> str | None:
        """Extract a display name from a URL, or None if blocklisted/self-referencing."""
        try:
            parsed = urlparse(url)
        except ValueError:
            return "External Service"
        host = parsed.hostname or parsed.netloc or parsed.path
        if not host:
            return "External Service"
        host = host.rstrip('.)').lower()
        if host in NON_SERVICE_HOSTS:
            return None
        repo_domain = self._get_repo_domain()
        if repo_domain and (host == repo_domain or host.endswith(f".{repo_domain}")):
            return None
        parts = host.split(".")
        if len(parts) >= 2:
            return parts[-2].replace("-", " ").replace("_", " ").title()
        return host.replace("-", " ").replace("_", " ").title()
