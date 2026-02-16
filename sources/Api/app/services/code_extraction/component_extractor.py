"""C4 Level 3 Component extraction and helper functions.

Extracts API endpoints, class-level components, and infrastructure
components from source code and manifests.
"""

import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from app.utils.fs_utils import limited_rglob
from app.services.code_extraction.python_ast_extractor import PythonASTExtractor
from app.domain.models.code_entities import CodeEntityType, CodeEntity
from app.services.c4.containers import is_deployable_service

logger = logging.getLogger(__name__)


def is_route_decorator(decorator: str) -> bool:
    """Check if decorator is a route decorator."""
    route_keywords = [
        'app.get', 'app.post', 'app.put', 'app.delete', 'app.patch',
        'router.get', 'router.post', 'router.put', 'router.delete', 'router.patch',
        'api.get', 'api.post', 'api.put', 'api.delete', 'api.patch',
    ]
    return any(kw in decorator.lower() for kw in route_keywords)


def extract_route_info_from_decorators(
    decorators: list[str], func_name: str
) -> Optional[dict]:
    """Extract route method and path from function decorators."""
    for decorator in decorators:
        lower_dec = decorator.lower()
        for method in ['get', 'post', 'put', 'delete', 'patch']:
            if f'.{method}' in lower_dec:
                path_match = re.search(r'["\']([^"\']+)["\']', decorator)
                if path_match:
                    path = path_match.group(1)
                else:
                    path = f"/api/{func_name.replace('_', '-')}"
                return {'method': method.upper(), 'path': path}
    return None


def classify_component(class_entity: CodeEntity) -> Optional[str]:
    """Classify a class as an architectural component type.

    Returns component type or None if not architecturally significant.
    """
    name = class_entity.name.lower()
    file_path = class_entity.file_path.lower()

    if 'config' in name or 'settings' in name or 'config' in file_path:
        return 'Configuration'
    if 'model' in name or 'schema' in name or 'entity' in name or 'models.py' in file_path:
        return 'Data Model'
    if 'service' in name or 'manager' in name or 'handler' in name:
        return 'Service'
    if 'controller' in name or 'api' in name or 'router' in name:
        return 'Controller'
    if 'gateway' in name or 'client' in name or 'adapter' in name:
        return 'Integration'
    if 'repository' in name or 'dao' in name:
        return 'Repository'

    base_classes = class_entity.attributes.get('base_classes', [])
    if base_classes:
        for base in base_classes:
            if any(keyword in str(base).lower() for keyword in ['base', 'abc', 'protocol']):
                return 'Base Class'

    decorators = class_entity.attributes.get('decorators', [])
    if decorators:
        return 'Decorated Component'

    return None


def infer_container_from_path(
    file_path: Path,
    repo_path: Path,
    containers: dict,
) -> Optional[str]:
    """Infer container name from file path."""
    try:
        rel_path = file_path.relative_to(repo_path)
        parts = rel_path.parts

        # Strategy 1: Check if file is under a known container
        for container_name, container_info in containers.items():
            container_path = container_info.get('path', '')
            if container_path and container_path != '.':
                if str(rel_path).startswith(container_path):
                    return container_name

        # Strategy 2: Match by name similarity
        file_path_str = str(rel_path).lower()
        best_match = None
        best_match_score = 0

        for container_name, container_info in containers.items():
            container_keywords = container_name.lower().replace('-', '_').split('_')
            match_score = sum(
                1 for keyword in container_keywords
                if keyword in file_path_str and len(keyword) > 2
            )
            if match_score > best_match_score:
                best_match = container_name
                best_match_score = match_score

        if best_match and best_match_score > 0:
            return best_match

        # Strategy 3: Walk up directory tree
        current = file_path.parent
        max_depth = 5
        depth = 0
        while current != repo_path and current.parent != repo_path.parent and depth < max_depth:
            if is_deployable_service(current):
                return current.name
            current = current.parent
            depth += 1

        # Strategy 4: Root container fallback
        root_container = next(
            (c['name'] for c in containers.values() if c.get('path') in {'.', ''}),
            None
        )
        if root_container:
            return root_container

        if containers:
            return next(iter(containers.keys()))

        return None
    except Exception:
        return None


def infer_infra_component_type(filename: str) -> str:
    """Infer infra component type from manifest filename."""
    name = filename.lower()
    if 'deployment' in name:
        return 'Deployment'
    if 'service' in name:
        return 'Service'
    if 'ingress' in name or 'route' in name:
        return 'Ingress'
    if 'configmap' in name:
        return 'ConfigMap'
    if 'secret' in name:
        return 'Secret'
    if 'statefulset' in name:
        return 'StatefulSet'
    if 'job' in name or 'cronjob' in name:
        return 'Job'
    if 'serviceaccount' in name:
        return 'Service Account'
    if 'role' in name or 'rbac' in name:
        return 'RBAC'
    return 'Infrastructure'


def extract_infra_components(container_path: Path, repo_path: Path) -> list[dict[str, Any]]:
    """Extract infra-level components from Helm/Kustomize manifests."""
    components = []

    chart_templates = container_path / 'chart' / 'templates'
    if chart_templates.exists():
        for file_path in chart_templates.rglob('*.yaml'):
            name = file_path.stem.replace('-', ' ').replace('_', ' ').title()
            comp_type = infer_infra_component_type(file_path.name)
            rel_path = file_path.relative_to(repo_path)
            components.append({
                'name': name,
                'component_type': comp_type,
                'file': str(rel_path),
            })

    kustomize_dir = container_path / 'kustomize'
    if kustomize_dir.exists():
        for file_path in kustomize_dir.rglob('*.yaml'):
            if file_path.name == 'kustomization.yaml':
                continue
            name = file_path.stem.replace('-', ' ').replace('_', ' ').title()
            comp_type = infer_infra_component_type(file_path.name)
            rel_path = file_path.relative_to(repo_path)
            components.append({
                'name': name,
                'component_type': comp_type,
                'file': str(rel_path),
            })

    return components


def add_infra_components_for_empty_containers(
    containers: dict,
    components: dict,
    components_by_container: dict[str, list],
    repo_path: Path,
) -> None:
    """Create minimal components from Helm/Kustomize manifests for empty containers."""
    for container_name, container in containers.items():
        if components_by_container.get(container_name):
            continue

        container_path = repo_path / container.get('path', '')
        infra_comps = extract_infra_components(container_path, repo_path)

        for comp in infra_comps:
            component_id = f"infra_{container_name}_{comp['name'].lower().replace(' ', '_')}"
            component = {
                'c4_level': 3,
                'type': 'component',
                'name': comp['name'],
                'component_type': comp['component_type'],
                'container': container_name,
                'file': comp.get('file'),
                'line_start': None,
                'signature': None,
                'documentation': None,
                'component_kind': 'Manifest',
            }
            components[component_id] = component
            components_by_container[container_name].append(component)


def apply_functional_grouping(
    components_by_container: dict[str, list],
    llm_manager: Any = None,
) -> None:
    """Use LLM to suggest functional groups for containers with >10 components."""
    for container, components in components_by_container.items():
        if len(components) <= 10:
            continue

        logger.info(f"Container '{container}' has {len(components)} components, applying LLM grouping...")

        if not llm_manager:
            logger.warning("LLM not available, skipping functional grouping")
            continue

        endpoint_paths = [
            comp.get('endpoint_path', comp.get('name', ''))
            for comp in components
        ]

        prompt = f"""Given these API endpoints from a '{container}' service:

{chr(10).join(f"- {path}" for path in endpoint_paths[:50])}

Suggest exactly 3 functional group names that best categorize these endpoints.
Examples: "Authentication", "User Management", "Data Processing", "Reporting", etc.

Return only 3 group names, one per line, no explanations."""

        try:
            response = llm_manager.generate_text(prompt, max_tokens=100, temperature=0.2, use_cache=True)
            if not response:
                continue

            group_names = [line.strip() for line in response.strip().split('\n') if line.strip()][:3]

            if len(group_names) == 3:
                logger.info(f"LLM suggested groups for {container}: {group_names}")
                _reassign_components_to_groups(container, components, group_names, llm_manager)
            else:
                logger.warning(f"LLM returned {len(group_names)} groups instead of 3, skipping")

        except Exception as e:
            logger.error(f"Failed to get LLM grouping: {e}")


def _reassign_components_to_groups(
    container: str,
    components: list,
    group_names: list[str],
    llm_manager: Any,
) -> None:
    """Reassign components to functional groups using LLM."""
    if not llm_manager or len(group_names) != 3:
        return

    endpoint_list = '\n'.join(
        f"{i+1}. {comp.get('endpoint_path', comp.get('name', ''))}"
        for i, comp in enumerate(components)
    )

    prompt = f"""Given these functional groups:
1. {group_names[0]}
2. {group_names[1]}
3. {group_names[2]}

Assign each endpoint to the most appropriate group (1, 2, or 3):

{endpoint_list}

Return only the group numbers (1, 2, or 3), one per line, matching the endpoint order."""

    try:
        response = llm_manager.generate_text(prompt, max_tokens=200, temperature=0.2, use_cache=True)
        if not response:
            return

        assignments = [line.strip() for line in response.strip().split('\n') if line.strip()]

        for i, comp in enumerate(components):
            if i < len(assignments):
                try:
                    group_idx = int(assignments[i]) - 1
                    if 0 <= group_idx < 3:
                        comp['functional_group'] = group_names[group_idx]
                except ValueError:
                    pass

    except Exception as e:
        logger.error(f"Failed to assign components to groups: {e}")


def link_components_to_containers(components: dict, containers: dict) -> None:
    """Create relationships between components and their containers."""
    for comp_id, component in components.items():
        container_name = component.get('container')
        for cont_id, container in containers.items():
            if container['name'] == container_name:
                if 'components' not in container:
                    container['components'] = []
                container['components'].append({
                    'id': comp_id,
                    'name': component['name'],
                    'type': component.get('component_type', 'Component')
                })
                component['container_id'] = cont_id
                break


def extract_level3_components(
    repo_path: Path,
    containers: dict,
    components: dict,
    detailed_entities: list,
    language_detectors: list,
    llm_manager: Any = None,
) -> None:
    """Extract Level 3: Components using AST for Python and LanguageDetectors for others.

    Modifies components dict in-place.
    """
    from app.services.code_extraction.language_detectors import PythonLanguageDetector

    logger.info("Extracting components using AST for Python and detectors for other languages...")
    components_by_container = defaultdict(list)

    # 1. Extract Python entry points using AST
    python_extractor = PythonASTExtractor(repo_path)
    python_files = list(limited_rglob(repo_path, "*.py"))

    excluded_dirs = {'node_modules', 'test', 'tests', '__tests__', '__pycache__', '.git', 'venv', '.venv'}
    python_files = [
        f for f in python_files
        if not any(excluded in f.parts for excluded in excluded_dirs)
    ]

    logger.info(f"Scanning {len(python_files)} Python files for entry point decorators...")

    for py_file in python_files:
        try:
            entities, _ = python_extractor.extract(py_file)

            for entity in entities:
                if entity.entity_type != CodeEntityType.FUNCTION:
                    continue

                decorators = entity.attributes.get('decorators', [])
                if not decorators:
                    continue

                is_entry = any(is_route_decorator(dec) for dec in decorators)

                if is_entry:
                    endpoint_info = extract_route_info_from_decorators(decorators, entity.name)
                    if endpoint_info:
                        container = infer_container_from_path(py_file, repo_path, containers)
                        rel_path = py_file.relative_to(repo_path)

                        component = {
                            'c4_level': 3,
                            'type': 'component',
                            'name': f"{endpoint_info['method']} {endpoint_info['path']}",
                            'component_type': 'API Endpoint',
                            'container': container,
                            'file': str(rel_path),
                            'line_start': entity.line_start,
                            'signature': entity.signature,
                            'documentation': entity.documentation,
                            'endpoint_path': endpoint_info['path'],
                            'endpoint_method': endpoint_info['method'],
                        }

                        component_id = f"endpoint_{entity.id}"
                        components[component_id] = component
                        components_by_container[container].append(component)

        except Exception as e:
            logger.warning(f"Failed to parse {py_file}: {e}")

    logger.info(f"Found {len(components)} Python entry point components")

    # 1b. Extract class-level components
    class_component_count = 0
    for entity in detailed_entities:
        if entity.entity_type != CodeEntityType.CLASS:
            continue

        component_type = classify_component(entity)
        if not component_type:
            continue

        try:
            file_path = Path(entity.file_path)
            container = infer_container_from_path(file_path, repo_path, containers)
            rel_path = file_path.relative_to(repo_path)
        except Exception:
            container = None
            rel_path = entity.file_path

        component_id = f"class_{entity.id}"
        if component_id in components:
            continue

        component = {
            'c4_level': 3,
            'type': 'component',
            'name': entity.name,
            'component_type': component_type,
            'container': container,
            'file': str(rel_path),
            'line_start': entity.line_start,
            'signature': entity.signature,
            'documentation': entity.documentation,
            'component_kind': 'Class',
        }

        components[component_id] = component
        components_by_container[container].append(component)
        class_component_count += 1

    if class_component_count:
        logger.info(f"Added {class_component_count} class-level components")

    # 2. Fall back to LanguageDetectors for non-Python files
    for detector in language_detectors:
        if isinstance(detector, PythonLanguageDetector):
            continue

        extensions = detector.get_file_extensions()
        for ext in extensions:
            files = list(limited_rglob(repo_path, f"*{ext}"))
            files = [
                f for f in files
                if not any(excluded in f.parts for excluded in excluded_dirs)
            ]

            logger.info(f"Scanning {len(files)} {ext} files with {detector.__class__.__name__}...")

            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    entry_points = detector.extract_entry_points(file_path, content)

                    for point in entry_points:
                        container = infer_container_from_path(file_path, repo_path, containers)
                        rel_path = file_path.relative_to(repo_path)

                        component = {
                            'c4_level': 3,
                            'type': 'component',
                            'name': point.get('name', 'Unknown'),
                            'component_type': 'API Endpoint',
                            'container': container,
                            'file': str(rel_path),
                            'line_number': point.get('line_number'),
                            'endpoint_path': point.get('path'),
                            'endpoint_method': point.get('method'),
                        }

                        component_id = f"endpoint_{file_path.name}_{point.get('name')}"
                        components[component_id] = component
                        components_by_container[container].append(component)

                except Exception as e:
                    logger.warning(f"Failed to parse {file_path}: {e}")

    logger.info(f"Total components extracted: {len(components)}")

    # 3. Add infra components for empty containers
    add_infra_components_for_empty_containers(
        containers, components, components_by_container, repo_path,
    )

    # 4. Group components by functional groups if >10
    apply_functional_grouping(components_by_container, llm_manager)
