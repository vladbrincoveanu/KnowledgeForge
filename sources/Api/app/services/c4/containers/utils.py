"""Utility functions for container detection."""

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


_URL_HOST_REGEX = re.compile(r"https?://([^/\s:]+)(?::\d+)?", re.IGNORECASE)
_HOST_PORT_REGEX = re.compile(r"\b([a-zA-Z0-9][a-zA-Z0-9-]*)(?:\.[a-zA-Z0-9.-]+)?:(\d{2,5})\b")
_HOSTNAME_REGEX = re.compile(r"\b([a-zA-Z0-9][a-zA-Z0-9-]{1,63})\b")
_OWNER_PATTERNS = (
    re.compile(r"^\s*owner\s*:\s*(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*team\s*:\s*(.+?)\s*$", re.IGNORECASE),
)
_CODEOWNERS_HANDLE_PATTERN = re.compile(r"@([a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)?)")


def infer_container_type(project_dir: Path) -> str:
    """Infer what type of container this is."""
    # Check for indicators
    if (project_dir / "Dockerfile").exists():
        # Read Dockerfile to guess type
        try:
            with open(project_dir / "Dockerfile") as f:
                content = f.read().lower()
                
                if 'node' in content or 'npm' in content:
                    return "Frontend (Node.js)"
                elif 'python' in content:
                    if 'fastapi' in content or 'flask' in content:
                        return "Backend API"
                    else:
                        return "Python Service"
                elif 'java' in content:
                    return "Java Service"
                elif 'go' in content:
                    return "Go Service"
                
                return "Containerized Service"
        except Exception:
            pass
    
    # Check for frontend indicators
    if (project_dir / "package.json").exists():
        try:
            with open(project_dir / "package.json") as f:
                data = json.load(f)
                deps = str(data.get('dependencies', {}))
                
                if 'react' in deps:
                    return "React Frontend"
                elif 'vue' in deps:
                    return "Vue Frontend"
                elif 'angular' in deps:
                    return "Angular Frontend"
                elif 'express' in deps:
                    return "Node.js Backend"
                
                return "JavaScript Application"
        except Exception:
            pass
    
    # Check for backend indicators
    if (project_dir / "pyproject.toml").exists():
        return "Python Service"
    
    # Check for database
    if 'db' in project_dir.name.lower() or 'database' in project_dir.name.lower():
        return "Database"
    
    # Check for worker/job
    if any(keyword in project_dir.name.lower() for keyword in ['worker', 'job', 'queue', 'task']):
        return "Background Worker"
    
    return "Service"


_MANIFEST_SKIP_DIRS = frozenset({
    ".git", "node_modules", "vendor", ".venv", "venv",
    "__pycache__", "dist", "build", "target",
})


def _detect_tech_from_manifests(directory: Path) -> str:
    """Check for build/package manifest files in a single directory."""
    if (directory / "package.json").exists():
        return "Node.js"
    if (directory / "pyproject.toml").exists() or (directory / "requirements.txt").exists():
        return "Python"
    if (directory / "pom.xml").exists():
        return "Java"
    if (directory / "build.gradle").exists() or (directory / "build.gradle.kts").exists():
        return "Java"
    if (directory / "go.mod").exists():
        return "Go"
    if list(directory.glob("*.csproj")) or list(directory.glob("*.sln")):
        return ".NET"
    if (directory / "Cargo.toml").exists():
        return "Rust"
    if list(directory.glob("*.tf")):
        return "Terraform"
    if (directory / "chart" / "Chart.yaml").exists() or (directory / "Chart.yaml").exists():
        return "Helm"
    return ""


def detect_technology_stack(project_dir: Path) -> str:
    """Detect primary technology stack."""
    # Manifest-based detection at root
    tech = _detect_tech_from_manifests(project_dir)
    if tech:
        return tech

    # One level deep: monorepo packages often keep manifests in a sub-package dir
    # (e.g. airbyte-cdk/python/pyproject.toml)
    try:
        for subdir in sorted(project_dir.iterdir()):
            if (subdir.is_dir()
                    and not subdir.name.startswith(".")
                    and subdir.name not in _MANIFEST_SKIP_DIRS):
                tech = _detect_tech_from_manifests(subdir)
                if tech:
                    return tech
    except OSError:
        pass

    # Fallback 1: infer from Dockerfile base image
    dockerfile = project_dir / "Dockerfile"
    if dockerfile.exists():
        tech = _detect_tech_from_dockerfile(dockerfile)
        if tech:
            return tech

    # Fallback 2: dominant source file extension
    tech = _detect_tech_from_source_files(project_dir)
    if tech:
        return tech

    return "Unknown"


_DOCKERFILE_IMAGE_MAP = (
    ("python", "Python"),
    ("node", "Node.js"),
    ("golang", "Go"),
    ("openjdk", "Java"),
    ("eclipse-temurin", "Java"),
    ("amazoncorretto", "Java"),
    ("rust", "Rust"),
    ("dotnet", ".NET"),
    ("mcr.microsoft.com/dotnet", ".NET"),
)


def _detect_tech_from_dockerfile(dockerfile: Path) -> str:
    """Parse the first FROM instruction and map the base image to a tech stack."""
    try:
        for line in dockerfile.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.upper().startswith("FROM "):
                image = stripped.split()[1].lower()
                for prefix, tech in _DOCKERFILE_IMAGE_MAP:
                    if image.startswith(prefix) or f"/{prefix}" in image:
                        return tech
                break
    except Exception:
        pass
    return ""


def _detect_tech_from_source_files(project_dir: Path) -> str:
    """Count source files by extension and return the dominant tech, or empty string.

    Checks root files first; if none found, also scans immediate subdirectories.
    """
    _EXT_TECH = {
        ".py": "Python",
        ".go": "Go",
        ".java": "Java",
        ".ts": "TypeScript",
        ".js": "JavaScript",
        ".rs": "Rust",
        ".cs": "C#",
        ".rb": "Ruby",
        ".sh": "Shell",
    }
    counts: dict[str, int] = {}

    def _scan(d: Path) -> None:
        try:
            for f in d.iterdir():
                if f.is_file() and f.suffix in _EXT_TECH:
                    counts[_EXT_TECH[f.suffix]] = counts.get(_EXT_TECH[f.suffix], 0) + 1
        except OSError:
            pass

    _scan(project_dir)

    if not counts:
        try:
            for subdir in project_dir.iterdir():
                if (subdir.is_dir()
                        and not subdir.name.startswith(".")
                        and subdir.name not in _MANIFEST_SKIP_DIRS):
                    _scan(subdir)
        except OSError:
            pass

    if not counts:
        return ""
    return max(counts, key=lambda t: counts[t])


def detect_service_owner(repo_path: Path, project_dir: Path) -> tuple[Optional[str], Optional[str]]:
    """Detect an owner and optional team for a single service directory."""
    readme_owner = _extract_owner_from_readme(project_dir)
    if readme_owner:
        codeowners_owner, codeowners_team = _extract_owner_from_codeowners(project_dir)
        return readme_owner, codeowners_team or codeowners_owner

    codeowners_owner, codeowners_team = _extract_owner_from_codeowners(project_dir)
    if codeowners_owner or codeowners_team:
        return codeowners_owner, codeowners_team

    root_readme_owner = _extract_owner_from_root_readme(repo_path, project_dir.name)
    if root_readme_owner:
        return root_readme_owner, None

    return None, None


def _extract_owner_from_readme(project_dir: Path) -> Optional[str]:
    for readme_name in ("README.md", "README.rst", "README.txt"):
        readme_path = project_dir / readme_name
        if not readme_path.exists():
            continue

        try:
            lines = readme_path.read_text(encoding='utf-8', errors='ignore').splitlines()
        except Exception:
            continue

        for line in lines[:80]:
            for pattern in _OWNER_PATTERNS:
                match = pattern.match(line)
                if match:
                    value = match.group(1).strip()
                    if value:
                        return value

    return None


def _extract_owner_from_codeowners(project_dir: Path) -> tuple[Optional[str], Optional[str]]:
    codeowners_path = project_dir / "CODEOWNERS"
    if not codeowners_path.exists():
        return None, None

    try:
        content = codeowners_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None, None

    handles = _CODEOWNERS_HANDLE_PATTERN.findall(content)
    if not handles:
        return None, None

    owner = handles[0]
    team = handles[1] if len(handles) > 1 else None
    return owner, team


def _extract_owner_from_root_readme(repo_path: Path, service_name: str) -> Optional[str]:
    for readme_name in ("README.md", "README.rst", "README.txt"):
        readme_path = repo_path / readme_name
        if not readme_path.exists():
            continue

        try:
            content = readme_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        match = re.search(
            rf"`?{re.escape(service_name)}`?\s+owned by\s+([^\n]+)",
            content,
            flags=re.IGNORECASE,
        )
        if match:
            owner = match.group(1).strip()
            if owner:
                return owner

    return None


def infer_protocol(project_dir: Path) -> str:
    """Infer communication protocol."""
    # Search for protocol indicators in source files
    protocols = set()
    
    # Check Python files
    for py_file in project_dir.rglob("*.py"):
        try:
            with open(py_file) as f:
                content = f.read(5000)  # First 5000 chars
                
                if 'grpc' in content.lower():
                    protocols.add('gRPC')
                if 'graphql' in content.lower():
                    protocols.add('GraphQL')
                if '@router' in content or '@app.get' in content or 'fastapi' in content.lower():
                    protocols.add('REST')
                if 'websocket' in content.lower():
                    protocols.add('WebSocket')
        except Exception:
            continue
        
        if protocols:
            break  # Found something, no need to scan more
    
    # Check JavaScript files
    for js_file in project_dir.rglob("*.js"):
        try:
            with open(js_file) as f:
                content = f.read(5000)
                
                if 'apollo' in content.lower() or 'graphql' in content.lower():
                    protocols.add('GraphQL')
                if 'express' in content.lower() or 'app.get' in content:
                    protocols.add('REST')
                if 'grpc' in content.lower():
                    protocols.add('gRPC')
        except Exception:
            continue
        
        if protocols:
            break
    
    if protocols:
        return ', '.join(sorted(protocols))
    
    return "HTTP"  # Default


def extract_container_description(project_dir: Path, llm_manager=None) -> str:
    """Extract a short description for a container from README/Chart.yaml or LLM."""
    description_sources = []
    readme_text = ""

    # README in container directory
    for readme_name in ["README.md", "README.rst", "README.txt"]:
        readme_path = project_dir / readme_name
        if readme_path.exists():
            try:
                with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(4000)
                readme_text = content
                description_sources.append(content)
                break
            except Exception:
                pass

    # Helm Chart.yaml description
    chart_yaml = project_dir / "chart" / "Chart.yaml"
    if chart_yaml.exists():
        try:
            with open(chart_yaml, 'r', encoding='utf-8', errors='ignore') as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and data.get('description'):
                chart_desc = str(data.get('description')).strip()
                if len(chart_desc) > 10:
                    return chart_desc
        except Exception:
            pass

    if readme_text:
        # Try first paragraph from README
        lines = [line.strip() for line in readme_text.splitlines()]
        paragraph = []
        for line in lines:
            if not line:
                if paragraph:
                    break
                continue
            if line.startswith('#') and not paragraph:
                continue
            paragraph.append(line)
        if paragraph:
            summary = ' '.join(paragraph).strip()
            if len(summary) > 12:
                return summary[:240]

        # Fallback to first descriptive line
        for line in lines:
            clean = line.lstrip('#').strip()
            if clean and len(clean) > 12:
                return clean[:200]

    # Optional LLM summary if available
    llm = llm_manager
    if llm and description_sources:
        prompt = f"""Summarize this service in one short sentence (max 20 words).

Content:
{description_sources[0][:1200]}

Answer:"""
        try:
            response = llm.generate_text(
                prompt,
                max_tokens=40,
                temperature=0.2,
                use_cache=True
            )
            if response:
                summary = response.strip()
                summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()
                summary = re.sub(r'^["\'\s]+|["\'\s]+$', '', summary)
                # Reject generic or meta responses
                if len(summary) < 12 or 'user' in summary.lower() and 'query' in summary.lower():
                    return ""
                # Keep only first sentence
                sentence = re.split(r'[.!?]', summary)[0].strip()
                if sentence:
                    return sentence[:200]
        except Exception:
            pass

    return ""


def get_repository_url(repo_path: Path, project_dir: Path) -> str:
    """Get GitLab/GitHub URL for this service subfolder.
    
    Constructs URL from git remote and project path.
    """
    try:
        # Get git remote URL
        result = subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            remote_url = result.stdout.strip()
            
            # Convert SSH to HTTPS URL
            if remote_url.startswith('git@'):
                # git@gitlab.com:user/repo.git -> https://gitlab.com/user/repo
                remote_url = remote_url.replace('git@', 'https://').replace('.com:', '.com/')
            
            # Remove .git suffix
            remote_url = remote_url.rstrip('.git')
            
            # Add path to service subfolder
            rel_path = project_dir.relative_to(repo_path)
            service_url = f"{remote_url}/-/tree/main/{rel_path}"
            
            return service_url
    
    except Exception as e:
        logger.debug(f"Failed to get repository URL: {e}")
    
    return ""


def extract_runtime_version(project_dir: Path) -> str:
    """Extract runtime version (Python 3.10, Node 20, etc.).
    
    Checks:
    - Dockerfile (FROM python:3.10)
    - pyproject.toml (requires-python = ">=3.10")
    - package.json (engines.node)
    - .python-version, .node-version files
    """
    # Check Dockerfile
    dockerfile = project_dir / "Dockerfile"
    if dockerfile.exists():
        try:
            with open(dockerfile) as f:
                content = f.read()
            
            # Find FROM statements
            from_pattern = r'FROM\s+([^\s]+)'
            matches = re.findall(from_pattern, content)
            
            for image in matches:
                # Extract version from image
                # Examples: python:3.10, node:20, openjdk:11
                if ':' in image:
                    base, version = image.split(':', 1)
                    
                    if 'python' in base:
                        return f"Python {version}"
                    elif 'node' in base:
                        return f"Node.js {version}"
                    elif 'openjdk' in base or 'java' in base:
                        return f"Java {version}"
                    elif 'golang' in base or 'go' in base:
                        return f"Go {version}"
        
        except Exception:
            pass
    
    # Check pyproject.toml
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomli
            with open(pyproject, 'rb') as f:
                data = tomli.load(f)
            
            # Check requires-python
            requires_python = data.get('project', {}).get('requires-python', '')
            if requires_python:
                # Extract version number
                version_match = re.search(r'[\d.]+', requires_python)
                if version_match:
                    return f"Python {version_match.group()}"
        
        except Exception:
            pass
    
    # Check package.json
    package_json = project_dir / "package.json"
    if package_json.exists():
        try:
            with open(package_json) as f:
                data = json.load(f)
            
            # Check engines
            engines = data.get('engines', {})
            if 'node' in engines:
                return f"Node.js {engines['node']}"
        
        except Exception:
            pass
    
    # Check version files
    version_files = {
        '.python-version': 'Python',
        '.node-version': 'Node.js',
        '.ruby-version': 'Ruby',
        '.java-version': 'Java',
    }
    
    for version_file, runtime in version_files.items():
        vfile = project_dir / version_file
        if vfile.exists():
            try:
                with open(vfile) as f:
                    version = f.read().strip()
                return f"{runtime} {version}"
            except Exception:
                pass
    
    return "Unknown"


def extract_health_endpoint(project_dir: Path) -> str:
    """Extract health check endpoint URL.
    
    Looks in:
    - values.yaml (ingress.host + health path)
    - deployment.yaml (liveness/readiness probes)
    - Source code (FastAPI health routes)
    """
    # Check values.yaml for ingress config
    values_file = project_dir / "chart" / "values.yaml"
    if values_file.exists():
        try:
            with open(values_file) as f:
                data = yaml.safe_load(f)
            
            # Extract host and health path
            host = None
            health_path = "/health"
            
            # Look for ingress host
            if 'ingress' in data:
                ingress = data['ingress']
                if 'host' in ingress:
                    host = ingress['host']
                elif 'hosts' in ingress and ingress['hosts']:
                    host = ingress['hosts'][0] if isinstance(ingress['hosts'], list) else ingress['hosts'].get('host')
            
            # Look for health check path
            if 'health' in data:
                health_config = data['health']
                if 'path' in health_config:
                    health_path = health_config['path']
            
            # Look for service config
            if 'service' in data:
                service = data['service']
                if 'port' in service:
                    port = service['port']
                    if host:
                        return f"https://{host}{health_path}"
            
            if host:
                return f"https://{host}{health_path}"
        
        except Exception:
            pass
    
    # Check deployment.yaml for readiness probe
    for deployment_file in project_dir.rglob("deployment.yaml"):
        try:
            with open(deployment_file) as f:
                content = f.read()
            
            # Look for httpGet path in readiness/liveness probe
            probe_pattern = r'(?:readinessProbe|livenessProbe):\s*httpGet:\s*path:\s*([^\s]+)'
            match = re.search(probe_pattern, content)
            
            if match:
                health_path = match.group(1)
                return f"http://localhost:8080{health_path}"
        
        except Exception:
            pass
    
    return ""


def extract_service_endpoint(project_dir: Path) -> str:
    """Extract main service endpoint/access path.
    
    Looks in:
    - values.yaml (ingress path, service port)
    - ingress.yaml (path rules)
    - README.md (documented endpoints)
    """
    # Check values.yaml for ingress config
    values_file = project_dir / "chart" / "values.yaml"
    if values_file.exists():
        try:
            with open(values_file) as f:
                data = yaml.safe_load(f)
            
            # Look for ingress configuration
            if 'ingress' in data:
                ingress = data['ingress']
                host = None
                path = "/"
                
                # Extract host
                if 'host' in ingress:
                    host = ingress['host']
                elif 'hosts' in ingress and ingress['hosts']:
                    host = ingress['hosts'][0] if isinstance(ingress['hosts'], list) else ingress['hosts'].get('host')
                
                # Extract path
                if 'path' in ingress:
                    path = ingress['path']
                elif 'paths' in ingress and ingress['paths']:
                    path = ingress['paths'][0] if isinstance(ingress['paths'], list) else "/"
                
                if host:
                    return f"https://{host}{path}"
                elif path and path != "/":
                    return path
        
        except Exception:
            pass
    
    # Check ingress.yaml for path configuration
    for ingress_file in project_dir.rglob("ingress.yaml"):
        try:
            with open(ingress_file) as f:
                content = f.read()
                data = yaml.safe_load(content)
            
            if data and isinstance(data, dict) and 'spec' in data:
                spec = data['spec']
                if 'rules' in spec and spec['rules']:
                    rule = spec['rules'][0]
                    host = rule.get('host', '')
                    
                    if 'http' in rule and 'paths' in rule['http']:
                        paths = rule['http']['paths']
                        if paths:
                            path = paths[0].get('path', '/')
                            if host:
                                return f"https://{host}{path}"
                            else:
                                return path
        
        except Exception:
            pass
    
    # Check README.md for documented endpoints
    readme_file = project_dir / "README.md"
    if readme_file.exists():
        try:
            with open(readme_file) as f:
                content = f.read()
            
            # Look for endpoint patterns like "Access at: http://..." or "URL: http://..."
            url_patterns = [
                r'(?:Access|URL|Endpoint|Available)(?:\s+at)?:\s*(https?://[^\s\)]+)',
                r'`(https?://[^\s`]+)`',
                r'\[(https?://[^\]]+)\]',
            ]
            
            for pattern in url_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            # Look for path patterns like "API: /api/v1"
            path_pattern = r'(?:API|Endpoint|Path):\s*(/[a-zA-Z0-9/_-]+)'
            match = re.search(path_pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        except Exception:
            pass
    
    return ""


def infer_type_from_image(image: str) -> str:
    """Infer container type from Docker image name."""
    image_lower = image.lower()

    if 'postgres' in image_lower:
        return "PostgreSQL Database"
    elif 'mongo' in image_lower:
        return "MongoDB Database"
    elif 'redis' in image_lower:
        return "Redis Cache"
    elif 'mssql' in image_lower or 'sqlserver' in image_lower:
        return "SQL Server Database"
    elif 'kafka' in image_lower:
        return "Message Broker"
    elif 'rabbitmq' in image_lower:
        return "Message Broker"
    elif 'elasticsearch' in image_lower or 'opensearch' in image_lower:
        return "Search Engine"
    elif 'nginx' in image_lower:
        return "Web Server"
    elif 'node' in image_lower:
        return "Node.js Service"
    elif 'python' in image_lower:
        return "Python Service"

    return "Service"


def extract_runtime_from_image(image: str) -> str:
    """Extract runtime version from Docker image tag.
    
    Examples:
    - python:3.10 -> Python 3.10
    - node:20-alpine -> Node.js 20
    - openjdk:11 -> Java 11
    """
    if not image or ':' not in image:
        return "Unknown"
    
    try:
        base, tag = image.split(':', 1)
        base_name = base.split('/')[-1]  # Handle registry prefix
        
        # Extract version number from tag
        version_match = re.search(r'(\d+\.?\d*)', tag)
        if version_match:
            version = version_match.group(1)
            
            if 'python' in base_name:
                return f"Python {version}"
            elif 'node' in base_name:
                return f"Node.js {version}"
            elif 'java' in base_name or 'openjdk' in base_name:
                return f"Java {version}"
            elif 'go' in base_name or 'golang' in base_name:
                return f"Go {version}"
            elif 'postgres' in base_name:
                return f"PostgreSQL {version}"
            elif 'mongo' in base_name:
                return f"MongoDB {version}"
            elif 'redis' in base_name:
                return f"Redis {version}"
            else:
                return f"{base_name.title()} {version}"
    
    except Exception:
        pass
    
    return "Unknown"


def extract_health_from_compose(service_config: dict) -> str:
    """Extract health check endpoint from docker-compose service config."""
    # Check for healthcheck
    if 'healthcheck' in service_config:
        healthcheck = service_config['healthcheck']
        if 'test' in healthcheck:
            test = healthcheck['test']
            # Parse health check command
            if isinstance(test, list):
                test_cmd = ' '.join(test)
            elif isinstance(test, str):
                test_cmd = test
            else:
                return ""
            
            # Extract URL from curl/wget commands
            url_match = re.search(r'https?://[^\s]+', test_cmd)
            if url_match:
                return url_match.group(0)
            
            # Extract path
            path_match = re.search(r'/[\w/-]+', test_cmd)
            if path_match:
                return f"http://localhost{path_match.group(0)}"
    
    return ""


def is_deployable_service(directory: Path) -> bool:
    """Check if a directory looks like a deployable service.

    Rules:
    - Dockerfile always qualifies.
    - Node.js must have package.json with scripts.start or bin field.
    - Python must have __main__.py or Dockerfile.
    - Helm/Kustomize/docker-compose qualify.
    - Bare pom.xml or pyproject.toml without entry points are ignored.
    """
    if not directory.is_dir():
        return False

    if (directory / 'Dockerfile').exists():
        return True

    if (directory / 'chart' / 'Chart.yaml').exists():
        return True

    if (directory / 'kustomize' / 'kustomization.yaml').exists():
        return True

    if (directory / 'docker-compose.yml').exists() or (directory / 'docker-compose.yaml').exists():
        return True

    package_json = directory / 'package.json'
    if package_json.exists():
        if _has_node_entrypoint(package_json):
            return True

    pyproject = directory / 'pyproject.toml'
    requirements = directory / 'requirements.txt'
    if pyproject.exists() or requirements.exists():
        if _has_python_entrypoint(directory):
            return True
        return False

    pom = directory / 'pom.xml'
    gradle = directory / 'build.gradle'
    gradle_kts = directory / 'build.gradle.kts'
    if pom.exists() or gradle.exists() or gradle_kts.exists():
        return False

    if (directory / 'go.mod').exists() or (directory / 'Cargo.toml').exists():
        return (directory / 'Dockerfile').exists()

    return False


def extract_internal_service_refs(text: str) -> set[str]:
    """Extract likely internal service hostnames from text.

    Matches URLs, host:port patterns, and service-like hostnames.
    Returns raw host tokens for further matching.
    """
    refs: set[str] = set()

    for host in _URL_HOST_REGEX.findall(text):
        refs.add(host)

    for host, _port in _HOST_PORT_REGEX.findall(text):
        refs.add(host)

    for host in _HOSTNAME_REGEX.findall(text):
        if host.isdigit():
            continue
        refs.add(host)

    cleaned: set[str] = set()
    for host in refs:
        normalized = host.strip().strip('"\'').strip()
        normalized = normalized.split("/")[0]
        if not normalized:
            continue
        cleaned.add(normalized)

    return cleaned


def _has_node_entrypoint(package_json_path: Path) -> bool:
    try:
        with open(package_json_path, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
    except Exception:
        return False

    scripts = data.get('scripts') or {}
    if isinstance(scripts, dict):
        start_cmd = scripts.get('start')
        if isinstance(start_cmd, str) and start_cmd.strip():
            return True

    bin_field = data.get('bin')
    if isinstance(bin_field, str) and bin_field.strip():
        return True
    if isinstance(bin_field, dict) and any(v for v in bin_field.values() if isinstance(v, str) and v.strip()):
        return True

    return False


def _has_python_entrypoint(directory: Path) -> bool:
    excluded_dirs = {'node_modules', 'test', 'tests', '__tests__', '__pycache__', '.git', 'venv', '.venv'}
    for main_file in directory.rglob('__main__.py'):
        if any(excluded in main_file.parts for excluded in excluded_dirs):
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# Relationship extraction utilities
# ---------------------------------------------------------------------------

PORT_PROTOCOL_MAP = {
    "5432": "PostgreSQL", "3306": "MySQL", "27017": "MongoDB",
    "6379": "Redis", "5672": "AMQP", "15672": "AMQP",
    "9092": "Kafka", "9200": "Elasticsearch", "50051": "gRPC",
    "443": "HTTPS", "80": "HTTP", "8080": "HTTP", "8000": "HTTP",
    "1433": "SQLServer", "4222": "NATS", "1521": "Oracle",
}

EVENT_BUS_IMAGES = {
    "kafka": ("Kafka", "publishes-to"),
    "rabbitmq": ("AMQP", "publishes-to"),
    "activemq": ("JMS", "publishes-to"),
    "mosquitto": ("MQTT", "publishes-to"),
    "nats": ("NATS", "publishes-to"),
    "pulsar": ("Pulsar", "publishes-to"),
    "redis": ("Redis", "uses"),
}


def infer_protocol_from_port(port: str) -> str:
    """Return protocol for a well-known port number, or 'TCP' if unknown."""
    return PORT_PROTOCOL_MAP.get(str(port).strip(), "TCP")


def normalize_depends_on(depends_on: Any) -> list[str]:
    """Normalize docker-compose depends_on to flat list of service names.

    Handles list form and dict form
    (depends_on: {db: {condition: service_healthy}}).
    """
    if isinstance(depends_on, list):
        return [str(s) for s in depends_on]
    if isinstance(depends_on, dict):
        return list(depends_on.keys())
    return []


def extract_named_volume(vol_spec: str) -> Optional[str]:
    """Return named volume name from a compose volume spec, or None for bind mounts."""
    if not vol_spec or not isinstance(vol_spec, str):
        return None
    source = vol_spec.split(':')[0].strip()
    if source.startswith(('.', '/', '~')):
        return None
    return source or None


def infer_relationship_type_from_image(image: str) -> tuple[str, str]:
    """Return (protocol, relationship_type) for event-bus images, else ("HTTP", "uses")."""
    image_lower = (image or "").lower()
    for keyword, result in EVENT_BUS_IMAGES.items():
        if keyword in image_lower:
            return result
    return "HTTP", "uses"


def flatten_dict(d: dict, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten nested dict to (dotted.key, value) pairs."""
    result: list[tuple[str, Any]] = []
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.extend(flatten_dict(v, full_key))
        else:
            result.append((full_key, v))
    return result


# ---------------------------------------------------------------------------
# Connection string / env-var relationship helpers
# ---------------------------------------------------------------------------

_STANDARD_URL_RE = re.compile(
    r"^(?P<scheme>postgresql|postgres|mongodb|redis|amqp|amqps|kafka|http|https|grpc|grpcs|mysql|sqlserver|jdbc)"
    r"(?:\+\w+)?://(?:[^@]+@)?(?P<host>[^/:?\s]+)(?::(?P<port>\d+))?(?:/(?P<database>[^?\s]*))?",
    re.IGNORECASE,
)
_SQLSERVER_RE = re.compile(
    r"[Ss]erver\s*=\s*(?:tcp:)?(?P<host>[^,;\s]+)(?:,(?P<port>\d+))?",
    re.IGNORECASE,
)
_JDBC_RE = re.compile(
    r"jdbc:(?P<scheme>[a-zA-Z0-9]+)://(?P<host>[^/:?\s]+)(?::(?P<port>\d+))?(?:/(?P<database>[^?\s]*))?",
    re.IGNORECASE,
)

_SCHEME_TO_PROTOCOL = {
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "amqp": "AMQP", "amqps": "AMQP",
    "kafka": "Kafka",
    "http": "HTTP", "https": "HTTPS",
    "grpc": "gRPC", "grpcs": "gRPC",
    "mysql": "MySQL",
    "sqlserver": "SQLServer",
    "jdbc": "JDBC",
}


def parse_connection_string(value: str) -> Optional[dict]:
    """Parse a connection string/URL to a dict with protocol, host, port, database.

    Supports:
    - Standard URL schemes: postgresql://, mongodb://, redis://, amqp://, kafka://,
      http://, https://, grpc://, mysql://
    - SQL Server: Server=tcp:host,port
    - JDBC: jdbc:postgresql://host:port/db

    Returns None when no recognisable pattern is found.
    """
    if not value or not isinstance(value, str):
        return None

    # JDBC check first (before generic URL, avoids matching "jdbc" as scheme)
    jdbc_m = _JDBC_RE.search(value)
    if jdbc_m:
        scheme = jdbc_m.group("scheme").lower()
        protocol = _SCHEME_TO_PROTOCOL.get(scheme, scheme.upper())
        return {
            "protocol": protocol,
            "host": jdbc_m.group("host"),
            "port": jdbc_m.group("port"),
            "database": jdbc_m.group("database") or None,
        }

    # Standard URL schemes
    url_m = _STANDARD_URL_RE.search(value)
    if url_m:
        scheme = url_m.group("scheme").lower()
        protocol = _SCHEME_TO_PROTOCOL.get(scheme, scheme.upper())
        return {
            "protocol": protocol,
            "host": url_m.group("host"),
            "port": url_m.group("port"),
            "database": url_m.group("database") or None,
        }

    # SQL Server connection string
    sql_m = _SQLSERVER_RE.search(value)
    if sql_m:
        return {
            "protocol": "SQLServer",
            "host": sql_m.group("host"),
            "port": sql_m.group("port"),
            "database": None,
        }

    return None


_DIRECTION_PRODUCER_TOKENS = frozenset({
    "PRODUCER", "PUBLISHER", "OUTPUT", "SEND", "SENDER", "PUBLISH", "EMIT", "WRITER",
})
_DIRECTION_CONSUMER_TOKENS = frozenset({
    "CONSUMER", "SUBSCRIBER", "INPUT", "RECEIVE", "RECEIVER", "LISTENER",
    "SUBSCRIBE", "READER", "INBOX",
})


def infer_direction_from_env_name(var_name: str) -> str:
    """Return relationship direction based on env-var name conventions.

    Splits on underscores and checks each token.
    Returns "publishes-to", "subscribes-to", or "uses" (default).
    """
    if not var_name:
        return "uses"
    tokens = set(var_name.upper().split("_"))
    if tokens & _DIRECTION_PRODUCER_TOKENS:
        return "publishes-to"
    if tokens & _DIRECTION_CONSUMER_TOKENS:
        return "subscribes-to"
    return "uses"
