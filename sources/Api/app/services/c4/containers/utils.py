"""Utility functions for container detection."""

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


_URL_HOST_REGEX = re.compile(r"https?://([^/\s:]+)(?::\d+)?", re.IGNORECASE)
_HOST_PORT_REGEX = re.compile(r"\b([a-zA-Z0-9][a-zA-Z0-9-]*)(?:\.[a-zA-Z0-9.-]+)?:(\d{2,5})\b")
_HOSTNAME_REGEX = re.compile(r"\b([a-zA-Z0-9][a-zA-Z0-9-]{1,63})\b")


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


def detect_technology_stack(project_dir: Path) -> str:
    """Detect primary technology stack."""
    if (project_dir / "package.json").exists():
        return "Node.js"
    elif (project_dir / "pyproject.toml").exists():
        return "Python"
    elif (project_dir / "pom.xml").exists():
        return "Java"
    elif (project_dir / "go.mod").exists():
        return "Go"
    elif (project_dir / "Cargo.toml").exists():
        return "Rust"
    
    return "Unknown"


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
