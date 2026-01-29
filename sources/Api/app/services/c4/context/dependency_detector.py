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
from pathlib import Path
from typing import Any

import tomli
import yaml

logger = logging.getLogger(__name__)


class DependencyDetector:
    """Detects external dependencies for C4 Context."""

    def __init__(self, repo_path: Path):
        """Initialize dependency detector.

        Args:
            repo_path: Path to repository
        """
        self.repo_path = Path(repo_path).resolve()

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

        # Detect from deployment files
        deps_from_deployment = self._parse_deployment_files()

        # Detect from README/docs
        deps_from_readme = self._parse_readme_dependencies()

        # Combine and deduplicate
        all_deps = (
            deps_from_configs
            + deps_from_helm
            + deps_from_env
            + deps_from_deployment
            + deps_from_readme
        )

        # Deduplicate by name
        seen = set()
        external_deps = []
        for dep in all_deps:
            name = dep['name']
            if name not in seen:
                external_deps.append(dep)
                seen.add(name)

        return external_deps

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
            except Exception as e:
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
            except Exception as e:
                logger.debug(f"Error parsing package.json: {e}")

        return deps

    def _parse_readme_dependencies(self) -> list[dict[str, Any]]:
        """Parse README/docs for external service references."""
        deps: list[dict[str, Any]] = []
        external_patterns = self._external_dependency_patterns()

        candidate_files = []
        for name in ["README.md", "README.rst", "README.txt"]:
            path = self.repo_path / name
            if path.exists():
                candidate_files.append(path)

        candidate_files.extend(self.repo_path.rglob("docs/*.md"))
        candidate_files.extend(self.repo_path.rglob("documentation/*.md"))

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
        external_patterns = self._external_dependency_patterns()

        def add_from_text(text: str, detected_from: str):
            lowered = text.lower()
            for pattern, (name, dep_type) in external_patterns.items():
                if pattern in lowered:
                    deps.append({
                        "name": name,
                        "type": dep_type,
                        "detected_from": detected_from,
                    })

        def add_from_url(url: str, detected_from: str):
            deps.append({
                "name": self._extract_service_name_from_url(url),
                "type": "external_service",
                "url": url,
                "detected_from": detected_from,
            })

        # Dockerfiles
        for dockerfile in self.repo_path.rglob("Dockerfile"):
            try:
                content = dockerfile.read_text(encoding="utf-8", errors="ignore")
                add_from_text(content, str(dockerfile.relative_to(self.repo_path)))
                for url in re.findall(r'https?://[^\s"\']+', content):
                    add_from_url(url, str(dockerfile.relative_to(self.repo_path)))
            except Exception:
                continue

        # docker-compose files
        for compose_file in self.repo_path.rglob("docker-compose*.y*ml"):
            try:
                data = yaml.safe_load(compose_file.read_text(encoding="utf-8", errors="ignore"))
                if not isinstance(data, dict):
                    continue
                services = data.get("services", {}) or {}
                for service in services.values():
                    if not isinstance(service, dict):
                        continue
                    image = service.get("image")
                    if isinstance(image, str):
                        add_from_text(image, str(compose_file.relative_to(self.repo_path)))
            except Exception:
                continue

        return deps

    def _parse_helm_values(self) -> list[dict[str, Any]]:
        """Extract external services from Helm values."""
        deps = []

        for values_file in self.repo_path.rglob("values.yaml"):
            try:
                with open(values_file) as f:
                    data = yaml.safe_load(f)

                if not data:
                    continue

                # Look for external URLs
                external_urls = self._find_external_urls(data)

                for url in external_urls:
                    name = self._extract_service_name_from_url(url)
                    deps.append({
                        'name': name,
                        'type': 'external_service',
                        'url': url,
                        'detected_from': str(values_file.relative_to(self.repo_path))
                    })

            except Exception as e:
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
                    name = self._extract_service_name_from_url(url)
                    deps.append({
                        'name': name,
                        'type': 'external_service',
                        'url': url,
                        'detected_from': env_file.name
                    })

            except Exception:
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
        # Remove protocol
        clean = url.replace('https://', '').replace('http://', '')
        # Get domain
        domain = clean.split('/')[0]
        # Get main part
        parts = domain.split('.')
        if len(parts) >= 2:
            return parts[-2].title()
        return domain
