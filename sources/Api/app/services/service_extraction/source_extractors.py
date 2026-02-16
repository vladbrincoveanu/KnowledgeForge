"""Source-specific service extraction strategies.

Each function scans a specific source type (docker-compose, kubernetes, etc.)
and returns discovered Service objects.
"""

import logging
import re
import xml.etree.ElementTree as ET
import yaml
import json
from pathlib import Path
from typing import Optional


def _find_target_framework_from_props(start_dir: Path, max_depth: int = 5) -> Optional[str]:
    """Walk up the directory tree looking for Directory.Build.props with <TargetFramework>."""
    current = start_dir.resolve()
    for _ in range(max_depth):
        props_file = current / "Directory.Build.props"
        if props_file.is_file():
            try:
                tree = ET.parse(str(props_file))
                for tag in ("TargetFramework", "TargetFrameworks"):
                    elem = tree.getroot().find(f".//{tag}")
                    if elem is not None and elem.text:
                        return elem.text.strip().split(";")[0]
            except ET.ParseError:
                pass
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None

from app.utils.fs_utils import limited_rglob
from app.domain.models.services import Service, ServiceStatus, ServiceTier
from app.services.service_extraction.extraction_helpers import (
    safe_read_file,
    extract_field_value,
    extract_status,
    extract_tier,
    extract_five_fields_from_config,
    extract_fields_from_code,
)

logger = logging.getLogger(__name__)


def extract_from_docker_compose(
    repo_root: Path,
    existing_services: list[Service],
    errors: list[str],
    warnings: list[str],
) -> list[Service]:
    """Extract services from docker-compose files."""
    services: list[Service] = []
    compose_files = (
        list(limited_rglob(repo_root, 'docker-compose*.yml')) +
        list(limited_rglob(repo_root, 'docker-compose*.yaml')) +
        list(limited_rglob(repo_root, 'compose.yml')) +
        list(limited_rglob(repo_root, 'compose.yaml'))
    )

    all_names = {s.name for s in existing_services}

    for compose_file in compose_files:
        try:
            with open(compose_file, 'r', encoding='utf-8') as f:
                content = f.read()
                compose_data = yaml.safe_load(content)

            if not compose_data or 'services' not in compose_data:
                continue

            rel_path = str(compose_file.relative_to(repo_root))

            for service_name, service_config in compose_data.get('services', {}).items():
                if service_name in all_names:
                    continue

                service_id = f"svc-{service_name}"

                # Get labels and environment for metadata extraction
                labels = service_config.get('labels', {})
                if isinstance(labels, list):
                    labels = {
                        item.split('=')[0]: item.split('=')[1] if '=' in item else None
                        for item in labels if isinstance(item, str)
                    }

                env = service_config.get('environment', {})
                if isinstance(env, list):
                    env = {
                        item.split('=')[0]: item.split('=')[1] if '=' in item else None
                        for item in env if isinstance(item, str)
                    }

                fields = extract_five_fields_from_config(service_config, labels=labels, env=env)

                service = Service(
                    id=service_id,
                    name=service_name,
                    display_name=service_name.replace('-', ' ').replace('_', ' ').title(),
                    domain=fields['domain'],
                    owner=fields['owner'],
                    status=fields['status'],
                    tier=fields['tier'],
                    data_class=fields['data_class'],
                    docker_compose_service=service_name,
                    file_path=rel_path,
                    source='docker_compose',
                )

                services.append(service)
                all_names.add(service_name)

        except Exception as e:
            error_msg = f"Failed to extract from {compose_file}: {e}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=True)

    return services


def extract_from_kubernetes(
    repo_root: Path,
    existing_services: list[Service],
    errors: list[str],
    warnings: list[str],
) -> list[Service]:
    """Extract services from Kubernetes manifests."""
    services: list[Service] = []
    all_names = {s.name for s in existing_services}

    k8s_patterns = [
        '**/k8s/**/*.yaml', '**/k8s/**/*.yml',
        '**/kubernetes/**/*.yaml', '**/kubernetes/**/*.yml',
        '**/manifests/**/*.yaml', '**/manifests/**/*.yml',
        '*.yaml', '*.yml',
    ]
    k8s_files = []
    for pattern in k8s_patterns:
        try:
            k8s_files.extend(list(repo_root.glob(pattern))[:50])
        except Exception as e:
            logger.warning(f"Error searching for k8s files with pattern {pattern}: {e}")

    seen = set()
    k8s_files = [f for f in k8s_files if f not in seen and not seen.add(f)]
    k8s_files = k8s_files[:200]

    for k8s_file in k8s_files:
        if 'docker-compose' in k8s_file.name.lower() or 'compose' in k8s_file.name.lower():
            continue

        try:
            with open(k8s_file, 'r', encoding='utf-8') as f:
                k8s_data = yaml.safe_load(f.read())

            if not k8s_data:
                continue

            kind = k8s_data.get('kind', '').lower()
            metadata = k8s_data.get('metadata', {})
            service_name = metadata.get('name', '')

            if not service_name or service_name in all_names:
                if kind not in ('service', 'deployment'):
                    continue
                if not service_name:
                    continue
                if service_name in all_names:
                    continue

            if kind in ('service', 'deployment'):
                annotations = metadata.get('annotations', {})
                labels_dict = metadata.get('labels', {})
                combined = {**labels_dict, **annotations}
                fields = extract_five_fields_from_config(combined)

                port = None
                if kind == 'service':
                    ports = k8s_data.get('spec', {}).get('ports', [])
                    if ports:
                        port = ports[0].get('port')

                source = 'kubernetes' if kind == 'service' else 'kubernetes_deployment'
                service_id = f"svc-{service_name}"
                rel_path = str(k8s_file.relative_to(repo_root))

                service = Service(
                    id=service_id,
                    name=service_name,
                    display_name=service_name.replace('-', ' ').title(),
                    domain=fields['domain'],
                    owner=fields['owner'],
                    status=fields['status'],
                    tier=fields['tier'],
                    data_class=fields['data_class'],
                    port=port,
                    file_path=rel_path,
                    source=source,
                )

                services.append(service)
                all_names.add(service_name)

        except yaml.YAMLError:
            continue
        except Exception as e:
            error_msg = f"Failed to extract from {k8s_file}: {e}"
            errors.append(error_msg)
            logger.info(error_msg)

    return services


def extract_from_api_routes(
    repo_root: Path,
    existing_services: list[Service],
    errors: list[str],
    warnings: list[str],
) -> list[Service]:
    """Extract services from API route files (FastAPI, Express, etc.)."""
    services: list[Service] = []
    all_names = {s.name for s in existing_services}

    route_patterns = [
        '**/routes/**/*.py', '**/routes/**/*.js', '**/routes/**/*.ts',
        '**/endpoint/**/*.py',
        '**/api/**/*.py', '**/api/**/*.js', '**/api/**/*.ts',
        '**/controllers/**/*.py', '**/controllers/**/*.js', '**/controllers/**/*.ts',
    ]

    route_files = []
    for pattern in route_patterns:
        route_files.extend(repo_root.glob(pattern))

    # Group by directory to identify services
    service_dirs: dict[str, list[Path]] = {}
    repo_parts = repo_root.parts

    for route_file in route_files:
        parts = route_file.parts
        for i, part in enumerate(parts):
            if part in ['routes', 'endpoint', 'api', 'controllers']:
                if i > 0:
                    service_name = parts[i-1] if i > len(repo_parts) else 'api'
                    if service_name not in service_dirs:
                        service_dirs[service_name] = []
                    service_dirs[service_name].append(route_file)
                    break

    for service_name, files in service_dirs.items():
        if service_name in all_names:
            continue

        port = None
        framework = None

        for file_path in files[:3]:
            content = safe_read_file(file_path, warnings)
            if not content:
                continue

            port_match = re.search(r'port\s*[=:]\s*(\d+)', content, re.IGNORECASE)
            if port_match:
                try:
                    port = int(port_match.group(1))
                except ValueError:
                    pass

            if 'fastapi' in content.lower() or 'from fastapi' in content.lower():
                framework = 'FastAPI'
            elif 'express' in content.lower() or 'require.*express' in content.lower():
                framework = 'Express'
            elif 'flask' in content.lower() or 'from flask' in content.lower():
                framework = 'Flask'
            elif 'django' in content.lower():
                framework = 'Django'

        # Extract fields from code
        domain = None
        owner = None
        status = ServiceStatus.UNKNOWN
        tier = ServiceTier.UNKNOWN
        data_class = None

        for file_path in files[:5]:
            content = safe_read_file(file_path, warnings)
            if not content:
                continue
            fields = extract_fields_from_code(content)
            if fields['domain'] and not domain:
                domain = fields['domain']
            if fields['owner'] and not owner:
                owner = fields['owner']
            if fields['status'] and fields['status'] != ServiceStatus.UNKNOWN and status == ServiceStatus.UNKNOWN:
                status = fields['status']
            if fields['tier'] and fields['tier'] != ServiceTier.UNKNOWN and tier == ServiceTier.UNKNOWN:
                tier = fields['tier']
            if fields['data_class'] and not data_class:
                data_class = fields['data_class']

        service_id = f"svc-{service_name}"
        rel_path = str(files[0].relative_to(repo_root).parent) if files else None

        service = Service(
            id=service_id,
            name=service_name,
            display_name=service_name.replace('-', ' ').replace('_', ' ').title(),
            domain=domain,
            owner=owner,
            status=status,
            tier=tier,
            data_class=data_class,
            port=port,
            file_path=rel_path,
            source='api_routes',
        )

        services.append(service)
        all_names.add(service_name)

    return services


def extract_from_service_configs(
    repo_root: Path,
    existing_services: list[Service],
    errors: list[str],
    warnings: list[str],
) -> list[Service]:
    """Extract services from service configuration files."""
    services: list[Service] = []
    all_names = {s.name for s in existing_services}

    config_patterns = [
        '**/service*.yml', '**/service*.yaml', '**/service*.json',
        '**/services.yml', '**/services.yaml',
    ]

    config_files = []
    for pattern in config_patterns:
        config_files.extend(repo_root.glob(pattern))

    for config_file in config_files:
        try:
            content = safe_read_file(config_file, warnings)
            if not content:
                continue

            if config_file.suffix in ['.yml', '.yaml']:
                data = yaml.safe_load(content)
            elif config_file.suffix == '.json':
                data = json.loads(content)
            else:
                continue

            if not isinstance(data, dict):
                continue

            rel_path = str(config_file.relative_to(repo_root))
            services_data = data.get('services', data)

            if isinstance(services_data, dict):
                for service_name, service_config in services_data.items():
                    if service_name in all_names:
                        continue

                    if isinstance(service_config, dict):
                        service_id = f"svc-{service_name}"
                        fields = extract_five_fields_from_config(service_config)

                        service = Service(
                            id=service_id,
                            name=service_name,
                            display_name=service_config.get('display_name') or service_name.replace('-', ' ').title(),
                            domain=fields['domain'],
                            owner=fields['owner'],
                            status=fields['status'],
                            tier=fields['tier'],
                            data_class=fields['data_class'],
                            file_path=rel_path,
                            source='service_config',
                        )

                        services.append(service)
                        all_names.add(service_name)

        except Exception as e:
            error_msg = f"Failed to extract from {config_file}: {e}"
            errors.append(error_msg)
            logger.info(error_msg)

    return services


def _extract_fields_from_config_files(
    config_paths: list[Path],
    warnings: list[str],
) -> dict:
    """Try to extract 5 primary fields from a list of config file paths."""
    domain = None
    owner = None
    status = ServiceStatus.UNKNOWN
    tier = ServiceTier.UNKNOWN
    data_class = None

    for config_path in config_paths:
        if not config_path.exists():
            continue

        content = safe_read_file(config_path, warnings)
        if not content:
            continue

        try:
            if config_path.suffix == '.json':
                config_data = json.loads(content)
            elif config_path.suffix in ['.yaml', '.yml']:
                config_data = yaml.safe_load(content)
            elif config_path.name == '__init__.py':
                # Extract from Python code comments/annotations
                fields = extract_fields_from_code(content)
                if fields['domain'] and not domain:
                    domain = fields['domain']
                if fields['owner'] and not owner:
                    owner = fields['owner']
                if fields['status'] and fields['status'] != ServiceStatus.UNKNOWN and status == ServiceStatus.UNKNOWN:
                    status = fields['status']
                if fields['tier'] and fields['tier'] != ServiceTier.UNKNOWN and tier == ServiceTier.UNKNOWN:
                    tier = fields['tier']
                if fields['data_class'] and not data_class:
                    data_class = fields['data_class']
                continue
            else:
                continue

            if isinstance(config_data, dict):
                fields = extract_five_fields_from_config(config_data)
                domain = domain or fields['domain']
                owner = owner or fields['owner']
                if status == ServiceStatus.UNKNOWN:
                    status = fields['status']
                if tier == ServiceTier.UNKNOWN:
                    tier = fields['tier']
                data_class = data_class or fields['data_class']
        except Exception:
            pass

    return {
        'domain': domain,
        'owner': owner,
        'status': status,
        'tier': tier,
        'data_class': data_class,
    }


def extract_from_microservice_patterns(
    repo_root: Path,
    existing_services: list[Service],
    errors: list[str],
    warnings: list[str],
) -> list[Service]:
    """Extract services from microservice directory patterns."""
    services: list[Service] = []
    all_names = {s.name for s in existing_services}

    service_dir_names = ['services', 'microservices', 'apps', 'packages', 'modules']

    for service_dir_name in service_dir_names:
        service_dir = repo_root / service_dir_name
        if not service_dir.exists() or not service_dir.is_dir():
            continue

        for subdir in service_dir.iterdir():
            if not subdir.is_dir():
                continue

            service_name = subdir.name
            if service_name in ['.git', 'node_modules', '__pycache__', '.venv', 'venv']:
                continue
            if service_name in all_names:
                continue

            has_service_files = any(
                (subdir / f).exists()
                for f in ['package.json', 'requirements.txt', 'pyproject.toml', 'Dockerfile',
                          'main.py', 'app.py', 'server.js', 'index.js',
                          'Program.cs', 'Startup.cs']
            ) or any(subdir.glob("*.csproj"))

            if not has_service_files:
                continue

            service_id = f"svc-{service_name}"
            rel_path = str(subdir.relative_to(repo_root))

            # Detect language and framework
            language = None
            framework = None

            if (subdir / 'package.json').exists():
                language = 'JavaScript'
                try:
                    with open(subdir / 'package.json', 'r') as f:
                        pkg_data = json.load(f)
                        deps = {**pkg_data.get('dependencies', {}), **pkg_data.get('devDependencies', {})}
                        if 'express' in deps:
                            framework = 'Express'
                        elif 'fastify' in deps:
                            framework = 'Fastify'
                except (OSError, json.JSONDecodeError, ValueError):
                    pass
            elif (subdir / 'requirements.txt').exists() or (subdir / 'pyproject.toml').exists():
                language = 'Python'
            elif any(subdir.glob("*.csproj")) or (subdir / 'Program.cs').exists() or (subdir / 'Startup.cs').exists():
                language = 'C#'

            config_paths = [
                subdir / 'package.json', subdir / 'pyproject.toml',
                subdir / 'config.json', subdir / 'service.json',
                subdir / 'service.yaml', subdir / 'service.yml',
            ]
            fields = _extract_fields_from_config_files(config_paths, warnings)

            service = Service(
                id=service_id,
                name=service_name,
                display_name=service_name.replace('-', ' ').replace('_', ' ').title(),
                domain=fields['domain'],
                owner=fields['owner'],
                status=fields['status'],
                tier=fields['tier'],
                data_class=fields['data_class'],
                language=language,
                file_path=rel_path,
                source='microservice_pattern',
            )

            services.append(service)
            all_names.add(service_name)

    return services


def extract_from_csproj(csproj_path: Path) -> dict:
    """Parse a .csproj file for service metadata.

    Args:
        csproj_path: Path to the .csproj file

    Returns:
        Dict with keys: name, dotnet_version, packages (list), project_refs (list)
    """
    result: dict = {
        "name": csproj_path.stem,
        "dotnet_version": None,
        "packages": [],
        "project_refs": [],
    }

    try:
        tree = ET.parse(str(csproj_path))
        root = tree.getroot()

        # AssemblyName overrides filename-based name
        assembly_elem = root.find(".//AssemblyName")
        if assembly_elem is not None and assembly_elem.text:
            result["name"] = assembly_elem.text.strip()

        # TargetFramework / TargetFrameworks (with Directory.Build.props fallback)
        tfm_raw = None
        for tag in ("TargetFramework", "TargetFrameworks"):
            elem = root.find(f".//{tag}")
            if elem is not None and elem.text:
                tfm_raw = elem.text.strip().split(";")[0]
                break
        if tfm_raw is None:
            tfm_raw = _find_target_framework_from_props(csproj_path.parent)
        if tfm_raw:
            result["dotnet_version"] = tfm_raw

        # PackageReference
        for ref in root.findall(".//PackageReference"):
            include = ref.get("Include", "")
            if include:
                result["packages"].append(include)

        # ProjectReference (internal deps)
        for ref in root.findall(".//ProjectReference"):
            include = ref.get("Include", "")
            if include:
                result["project_refs"].append(include.replace("\\", "/"))

    except ET.ParseError as e:
        logger.warning("Failed to parse %s: %s", csproj_path, e)

    return result


def extract_from_sln(sln_path: Path) -> list[str]:
    """Parse a .sln file to extract paths to all .csproj sub-projects.

    Args:
        sln_path: Path to the .sln file

    Returns:
        List of absolute paths to .csproj files referenced in the solution
    """
    csproj_paths: list[str] = []
    sln_dir = sln_path.parent

    # Solution file Project entries look like:
    # Project("{FAE04EC0-...}") = "MyProject", "src\MyProject\MyProject.csproj", "{...}"
    project_pattern = re.compile(
        r'^Project\(["\{][^)]*\)\s*=\s*"[^"]*",\s*"([^"]+\.csproj)"',
        re.IGNORECASE,
    )

    try:
        for line in sln_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = project_pattern.match(line.strip())
            if match:
                relative = match.group(1).replace("\\", "/")
                abs_path = (sln_dir / relative).resolve()
                csproj_paths.append(str(abs_path))
    except (OSError, ValueError) as e:
        logger.warning("Failed to parse %s: %s", sln_path, e)

    return csproj_paths


def extract_from_top_level_directories(
    repo_root: Path,
    existing_services: list[Service],
    errors: list[str],
    warnings: list[str],
) -> list[Service]:
    """Extract services from top-level directories (for monorepos)."""
    services: list[Service] = []
    all_names = {s.name for s in existing_services}

    logger.info("Extracting services from top-level directories")

    skip_dirs = {
        '.git', '.github', '.vscode', '.idea', 'node_modules', '__pycache__',
        '.venv', 'venv', 'env', '.env', 'dist', 'build', 'target', 'out',
        'docs', 'documentation', 'tests', 'test', 'testing', 'spec', 'specs',
        'scripts', 'tools', 'utils', 'utilities', 'migrations', 'locale',
        'static', 'assets', 'media', 'public', 'resources', 'config', 'conf',
        'settings', 'deploy', 'deployment', 'ci', '.circleci', '.travis',
        'examples', 'sample', 'samples', 'demo', 'demos', 'tmp', 'temp',
        'log', 'logs', 'var', 'cache', '.cache', 'coverage', '.coverage',
        'vendor', 'lib', 'libs', 'third_party', 'third-party', 'external'
    }

    service_indicators = [
        '__init__.py', 'apps.py', 'models.py', 'views.py', 'urls.py',
        'package.json', 'setup.py', 'pyproject.toml', 'Dockerfile',
        'service.yml', 'service.yaml', 'main.py', 'app.py',
        'index.js', 'server.js',
        'Program.cs', 'Startup.cs',
    ]

    for item in repo_root.iterdir():
        if not item.is_dir():
            continue

        dir_name = item.name
        if dir_name.startswith('.') or dir_name.lower() in skip_dirs:
            continue
        if dir_name in all_names:
            continue

        has_service_files = (
            any((item / indicator).exists() for indicator in service_indicators)
            or any(item.glob("*.csproj"))
            or any(item.glob("*.sln"))
        )

        if not has_service_files:
            try:
                for subdir in item.iterdir():
                    if subdir.is_dir() and (subdir / '__init__.py').exists():
                        has_service_files = True
                        break
            except (PermissionError, OSError) as e:
                logger.warning(f"Error checking subdirectories in {item}: {e}")

        if not has_service_files:
            continue

        service_id = f"svc-{dir_name}"
        rel_path = str(item.relative_to(repo_root))

        # Detect language and framework
        language = None
        framework = None

        if (item / '__init__.py').exists() or (item / 'setup.py').exists() or (item / 'pyproject.toml').exists():
            language = 'Python'
            if (item / 'apps.py').exists() or (item / 'models.py').exists():
                framework = 'Django'
            elif (item / 'app.py').exists():
                try:
                    content = safe_read_file(item / 'app.py', warnings)
                    if content and ('from flask' in content.lower() or 'Flask(' in content):
                        framework = 'Flask'
                except Exception:
                    pass
        elif (item / 'package.json').exists():
            language = 'JavaScript'
            try:
                with open(item / 'package.json', 'r') as f:
                    pkg_data = json.load(f)
                    deps = {**pkg_data.get('dependencies', {}), **pkg_data.get('devDependencies', {})}
                    if 'django' in deps or 'djangorestframework' in deps:
                        framework = 'Django'
                    elif 'express' in deps:
                        framework = 'Express'
                    elif 'fastify' in deps:
                        framework = 'Fastify'
                    elif 'react' in deps:
                        framework = 'React'
            except (OSError, json.JSONDecodeError, ValueError):
                pass
        elif (
            any(item.glob("*.csproj"))
            or (item / 'Program.cs').exists()
            or (item / 'Startup.cs').exists()
        ):
            language = 'C#'
            framework = 'ASP.NET Core'

        config_paths = [
            item / 'package.json', item / 'pyproject.toml', item / 'setup.py',
            item / 'config.json', item / 'service.json',
            item / 'service.yaml', item / 'service.yml',
            item / '__init__.py',
        ]
        fields = _extract_fields_from_config_files(config_paths, warnings)

        service = Service(
            id=service_id,
            name=dir_name,
            display_name=dir_name.replace('-', ' ').replace('_', ' ').title(),
            domain=fields['domain'],
            owner=fields['owner'],
            status=fields['status'],
            tier=fields['tier'],
            data_class=fields['data_class'],
            language=language,
            framework=framework,
            file_path=rel_path,
            source='top_level_directory',
        )

        services.append(service)
        all_names.add(dir_name)
        logger.info(f"Extracted service from top-level directory: {dir_name}")

    return services
