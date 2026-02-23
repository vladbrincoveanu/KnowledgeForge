"""External dependency detection for C4 Context level.

Detects external services and dependencies from:
- Package manifests (package.json, pyproject.toml, etc.)
- Deployment files (docker-compose, Kubernetes, Dockerfile)
- Environment files (.env)
- Helm values
- README documentation
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

import tomli
import yaml

from app.utils.fs_utils import limited_rglob
from .dependency_classifier import DependencyClassifier


# NuGet package prefix → (external service label, dep type)
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
    # EF Core provider mappings
    "Microsoft.EntityFrameworkCore.SqlServer": ("SQL Server", "database"),
    "Microsoft.EntityFrameworkCore.Npgsql": ("PostgreSQL", "database"),
    "Microsoft.EntityFrameworkCore.Cosmos": ("Azure Cosmos DB", "database"),
    "Pomelo.EntityFrameworkCore.MySql": ("MySQL", "database"),
    # Additional cloud/infra
    "AspNetCore.HealthChecks.SqlServer": ("SQL Server", "database"),
    "AspNetCore.HealthChecks.Redis": ("Redis", "cache"),
    "AspNetCore.HealthChecks.Kafka": ("Kafka", "messaging"),
    "Microsoft.AspNetCore.SignalR.StackExchangeRedis": ("Redis", "cache"),
    "Serilog": ("Serilog (Logging)", "logging"),
    "OpenTelemetry": ("OpenTelemetry", "observability"),
    "Consul": ("Consul", "service-discovery"),
}

logger = logging.getLogger(__name__)


class DependencyDetector:
    """Detects external dependencies for C4 Context."""

    _INTERNAL_HOST_RE = re.compile(
        r'^(\*|localhost|0\.0\.0\.0|127\.\d+\.\d+\.\d+|\d{1,3}(?:\.\d{1,3}){3})'
        r'(:\d+)?$'
    )

    def __init__(self, repo_path: Path, llm_manager=None, enable_classification: bool = True):
        """Initialize dependency detector.

        Args:
            repo_path: Path to repository
            llm_manager: Optional LLM manager for classification (supports OpenAI or local LLM)
            enable_classification: Whether to enable LLM classification (default: True)
        """
        self.repo_path = Path(repo_path).resolve()
        self.classifier = DependencyClassifier(llm_manager) if enable_classification else None

    def detect_external_dependencies(self) -> list[dict[str, Any]]:
        """Detect external service dependencies.

        Looks for:
        - Cloud providers (AWS, Azure, GCP)
        - Databases (PostgreSQL, MongoDB, Redis)
        - Payment providers (Stripe, PayPal)
        - Auth providers (Auth0, Okta)
        - APIs and SaaS services
        """
        # Parse dependencies from config files
        deps_from_configs = self._parse_dependency_files()

        # Detect from values.yaml (Helm charts)
        deps_from_helm = self._parse_helm_values()

        # Detect from .env files
        deps_from_env = self._parse_env_files()

        # Detect from deployment files (kept separate; not "external systems" at C4 context level)
        # However, docker-compose often encodes *technical platforms* (Postgres/Redis/Kafka/etc).
        # We infer those platform dependencies from images, but never expose raw container images
        # as "external services" in the Context diagram.
        deps_from_deployment = self._infer_technical_platforms_from_deployment()

        # Detect from README/docs
        deps_from_readme = self._parse_readme_dependencies()

        # Detect from .csproj NuGet references
        deps_from_nuget = self._parse_nuget_dependencies()

        # Combine and deduplicate
        all_deps = (
            deps_from_configs
            + deps_from_helm
            + deps_from_env
            + deps_from_deployment
            + deps_from_readme
            + deps_from_nuget
        )

        # Deduplicate by name
        seen = set()
        external_deps = []
        for dep in all_deps:
            raw_name = dep.get('name', '')
            name = self._normalize_logical_name(raw_name)
            if not name or name.startswith('$') or name in seen:
                continue
            dep['name'] = name
            external_deps.append(dep)
            seen.add(name)

        # Classify dependencies if classifier enabled
        if self.classifier:
            logger.info(f"Classifying {len(external_deps)} external dependencies...")
            classified_deps = []
            
            for dep in external_deps:
                classification = self.classifier.classify_dependency(
                    name=dep.get('name', ''),
                    dep_type=dep.get('type', ''),
                    detected_from=dep.get('detected_from', ''),
                    context=dep.get('context', '')
                )
                
                # Add classification fields to dependency
                dep['dependency_type'] = classification.type.value
                dep['classification_confidence'] = classification.confidence
                dep['classification_reasoning'] = classification.reasoning
                
                classified_deps.append(dep)
            
            return classified_deps
        
        return external_deps

    def _infer_technical_platforms_from_deployment(self) -> list[dict[str, Any]]:
        """Infer well-known technical platforms from Docker/compose without leaking docker artifacts.

        Output is *platform names* (e.g. 'PostgreSQL'), not images.
        """
        platforms: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(name: str, dep_type: str, detected_from: str, context: str):
            if name in seen:
                return
            platforms.append(
                {
                    "name": name,
                    "type": dep_type,
                    "dependency_type": "TECHNICAL_INFRA",
                    "classification_confidence": 0.9,
                    "classification_reasoning": "Inferred from deployment configuration (docker/compose).",
                    # Do not leak docker/compose paths into context-level "externals".
                    "detected_from": "deployment",
                    "context": context,
                }
            )
            seen.add(name)

        def classify_image(image: str) -> Optional[tuple[str, str]]:
            s = image.lower()
            # Databases
            if "postgres" in s:
                return ("PostgreSQL", "database")
            if "mcr.microsoft.com/mssql" in s or "sqlserver" in s or "mssql" in s:
                return ("SQL Server", "database")
            if "mysql" in s:
                return ("MySQL", "database")
            if "mariadb" in s:
                return ("MariaDB", "database")
            if "mongo" in s:
                return ("MongoDB", "database")
            # Cache
            if re.search(r'(^|[/:.-])redis([/:.-]|$)', s):
                return ("Redis", "cache")
            # Messaging/streaming
            if "rabbitmq" in s:
                return ("RabbitMQ", "messaging")
            if "kafka" in s or "cp-kafka" in s:
                return ("Kafka", "messaging")
            if "zookeeper" in s:
                return ("ZooKeeper", "messaging")
            # Observability/logging
            if "grafana" in s:
                return ("Grafana", "monitoring")
            if "prometheus" in s:
                return ("Prometheus", "monitoring")
            if "loki" in s:
                return ("Loki", "logging")
            return None

        # docker-compose images
        for compose_file in limited_rglob(self.repo_path, "docker-compose*.y*ml"):
            try:
                rel = str(compose_file.relative_to(self.repo_path))
                data = yaml.safe_load(
                    compose_file.read_text(encoding="utf-8", errors="ignore")
                )
                if not isinstance(data, dict):
                    continue
                services = data.get("services", {}) or {}
                if not isinstance(services, dict):
                    continue

                for svc_name, svc in services.items():
                    if not isinstance(svc, dict):
                        continue
                    image = svc.get("image")
                    if not isinstance(image, str) or not image.strip():
                        continue
                    image = image.strip()
                    classified = classify_image(image)
                    if not classified:
                        continue
                    name, dep_type = classified
                    add(
                        name=name,
                        dep_type=dep_type,
                        detected_from=rel,
                        context=f"Inferred from docker-compose service '{svc_name}' image.",
                    )
            except (OSError, yaml.YAMLError):
                continue

        return platforms

    def detect_deployment_dependencies(self) -> list[dict[str, Any]]:
        """Return internal deployment/runtime dependencies (Docker/compose).

        These are useful as evidence of infrastructure used by the system, but they are
        not external business systems and should not be placed in the C4 System Context
        diagram as "external services".
        """
        return self._parse_deployment_files()

    def _parse_nuget_dependencies(self) -> list[dict[str, Any]]:
        """Scan .csproj files for NuGet packages and map them to external services."""
        deps: list[dict[str, Any]] = []
        seen_names: set[str] = set()

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
                    # Match against NUGET_DEPENDENCY_MAP by prefix
                    for prefix, (service_name, dep_type) in NUGET_DEPENDENCY_MAP.items():
                        if pkg.lower().startswith(prefix.lower()):
                            if service_name not in seen_names:
                                deps.append({
                                    "name": service_name,
                                    "type": dep_type,
                                    "detected_from": rel_path,
                                    "context": f"NuGet package: {pkg}",
                                })
                                seen_names.add(service_name)
                            break
            except ET.ParseError as e:
                logger.debug("Could not parse %s: %s", csproj, e)

        return deps

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
        """Return known external dependency patterns."""
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
        }

    def _parse_dependency_files(self) -> list[dict[str, Any]]:
        """Parse package manifests for external dependencies."""
        deps = []
        external_patterns = self._external_dependency_patterns()

        # Scan pyproject.toml
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject, 'rb') as f:
                    data = tomli.load(f)

                    # Check dependencies
                    project_deps = data.get('project', {}).get('dependencies', [])
                    poetry_deps = data.get('tool', {}).get('poetry', {}).get('dependencies', {})

                    all_deps_text = str(project_deps) + str(poetry_deps)

                    for pattern, (name, dep_type) in external_patterns.items():
                        if pattern in all_deps_text.lower():
                            deps.append({
                                'name': name,
                                'type': dep_type,
                                'detected_from': 'pyproject.toml'
                            })
            except (OSError, ValueError) as e:
                logger.debug(f"Error parsing pyproject.toml: {e}")

        # Scan package.json
        package_json = self.repo_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)

                    all_deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
                    all_deps_text = str(all_deps)

                    for pattern, (name, dep_type) in external_patterns.items():
                        if pattern in all_deps_text.lower():
                            deps.append({
                                'name': name,
                                'type': dep_type,
                                'detected_from': 'package.json'
                            })
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.debug(f"Error parsing package.json: {e}")

        return deps

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
                        alerts.append({
                            "dependency": name,
                            "version": version,
                            "issue": "range_version",
                            "source": str(req_file.relative_to(self.repo_path)),
                        })
                else:
                    pkg = re.split(r"\s+", raw, 1)[0]
                    issue = self._classify_version(raw)
                    if issue:
                        alerts.append({
                            "dependency": pkg,
                            "version": raw,
                            "issue": issue,
                            "source": str(req_file.relative_to(self.repo_path)),
                        })
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
                alerts.append({
                    "dependency": name,
                    "version": version,
                    "issue": issue,
                    "source": "pyproject.toml",
                })

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
                alerts.append({
                    "dependency": name,
                    "version": version,
                    "issue": issue,
                    "source": "pyproject.toml",
                })

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
                    alerts.append({
                        "dependency": name,
                        "version": version_str,
                        "issue": issue,
                        "source": f"package.json:{section}",
                    })

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
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*([<>=!~]{1,2})\s*([^\s]+)$", raw)
        if match:
            _, op, version = match.groups()
            if op == "==":
                return name, version
            return name, raw
        return name, raw

    def _parse_readme_dependencies(self) -> list[dict[str, Any]]:
        """Parse README/docs for external service references."""
        deps: list[dict[str, Any]] = []
        external_patterns = self._external_dependency_patterns()

        candidate_files = []
        for name in ["README.md", "README.rst", "README.txt"]:
            path = self.repo_path / name
            if path.exists():
                candidate_files.append(path)

        from app.utils.fs_utils import limited_rglob
        candidate_files.extend(list(limited_rglob(self.repo_path, "docs/*.md")))
        candidate_files.extend(list(limited_rglob(self.repo_path, "documentation/*.md")))

        for doc in candidate_files:
            try:
                content = doc.read_text(encoding="utf-8", errors="ignore").lower()
                for pattern, (name, dep_type) in external_patterns.items():
                    if pattern in content:
                        deps.append({
                            "name": name,
                            "type": dep_type,
                            "detected_from": str(doc.relative_to(self.repo_path)),
                        })
            except Exception:
                continue

        return deps

    def _parse_deployment_files(self) -> list[dict[str, Any]]:
        """Parse deployment files for dependencies."""
        deps: list[dict[str, Any]] = []

        from app.utils.fs_utils import limited_rglob

        # Dockerfiles: capture base images used (runtime/build dependencies).
        for dockerfile in limited_rglob(self.repo_path, "Dockerfile"):
            try:
                rel = str(dockerfile.relative_to(self.repo_path))
                content = dockerfile.read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    m = re.match(r'^\s*FROM\s+([^\s]+)', line, re.IGNORECASE)
                    if not m:
                        continue
                    image = m.group(1).strip()
                    deps.append(
                        {
                            "name": image,
                            "type": "container_image",
                            "scope": "deployment",
                            "is_external": False,
                            "detected_from": rel,
                            "context": f"Docker base image: {image}",
                        }
                    )
            except (OSError, ValueError):
                continue

        # docker-compose: capture service images (internal infra used at runtime).
        for compose_file in limited_rglob(self.repo_path, "docker-compose*.y*ml"):
            try:
                rel = str(compose_file.relative_to(self.repo_path))
                data = yaml.safe_load(
                    compose_file.read_text(encoding="utf-8", errors="ignore")
                )
                if not isinstance(data, dict):
                    continue
                services = data.get("services", {}) or {}
                if not isinstance(services, dict):
                    continue

                for svc_name, svc in services.items():
                    if not isinstance(svc, dict):
                        continue
                    image = svc.get("image")
                    if not isinstance(image, str) or not image.strip():
                        continue
                    image = image.strip()
                    deps.append(
                        {
                            "name": image,
                            "type": "container_image",
                            "scope": "deployment",
                            "is_external": False,
                            "detected_from": rel,
                            "context": f"docker-compose service '{svc_name}' image: {image}",
                        }
                    )
            except (OSError, yaml.YAMLError):
                continue

        return deps

    def _parse_helm_values(self) -> list[dict[str, Any]]:
        """Extract external services from Helm values."""
        deps = []

        for values_file in limited_rglob(self.repo_path,"values.yaml"):
            try:
                with open(values_file) as f:
                    data = yaml.safe_load(f)

                if not data:
                    continue

                # Look for external URLs
                external_urls = self._find_external_urls(data)

                for url in external_urls:
                    if self._is_internal_url(url):
                        continue
                    name = self._extract_service_name_from_url(url)
                    deps.append({
                        'name': name,
                        'type': 'external_service',
                        'url': url,
                        'detected_from': str(values_file.relative_to(self.repo_path))
                    })

            except (OSError, yaml.YAMLError) as e:
                logger.debug(f"Error parsing {values_file}: {e}")

        return deps

    def _parse_env_files(self) -> list[dict[str, Any]]:
        """Parse .env files for external service references."""
        deps = []

        env_files = list(self.repo_path.glob("*.env")) + list(self.repo_path.glob(".env*"))

        url_pattern = r'https?://[^\s"\']+'

        for env_file in env_files:
            try:
                with open(env_file, 'r') as f:
                    content = f.read()

                # Find URLs
                urls = re.findall(url_pattern, content)

                for url in urls:
                    if self._is_internal_url(url):
                        continue
                    name = self._extract_service_name_from_url(url)
                    deps.append({
                        'name': name,
                        'type': 'external_service',
                        'url': url,
                        'detected_from': env_file.name
                    })

            except (OSError, ValueError):
                pass

        return deps

    def _find_external_urls(self, data: dict, path: str = "") -> list[str]:
        """Recursively find external URLs in nested dict."""
        urls = []

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    if value.startswith(('http://', 'https://')):
                        urls.append(value)
                else:
                    urls.extend(self._find_external_urls(value, f"{path}.{key}"))
        elif isinstance(data, list):
            for item in data:
                urls.extend(self._find_external_urls(item, path))

        return urls

    def _extract_service_name_from_url(self, url: str) -> str:
        """Extract service name from URL."""
        clean = url.replace('https://', '').replace('http://', '')
        domain = clean.split('/')[0]
        return self._normalize_logical_name(domain)

    def _is_internal_url(self, url: str) -> bool:
        """Return True for local/wildcard bindings that are not real external services.

        Filters out:
        - http://*:PORT   (.NET all-interface bindings)
        - http://localhost:PORT
        - http://0.0.0.0:PORT
        - http://127.x.x.x:PORT
        - http://192.168.x.x:PORT  (any bare IP)
        - https://${VAR}/...       (unresolved template variables)
        """
        clean = url.replace('https://', '').replace('http://', '').split('/')[0]
        if clean.startswith('$'):
            return True
        return bool(self._INTERNAL_HOST_RE.match(clean))

    def _normalize_logical_name(self, value: str) -> str:
        """Normalize raw host/service identifiers to stable logical names."""
        label = str(value or '').strip()
        if not label:
            return ""

        label = re.sub(r'^https?://', '', label, flags=re.IGNORECASE)
        label = label.split('/', 1)[0]
        label = re.sub(r':\d{2,5}$', '', label)

        # Keep single host token for label, convert common separators
        head = label.split('.', 1)[0]
        head = head.replace('_', ' ').replace('-', ' ').strip()
        if not head:
            return ""
        return head.title()
