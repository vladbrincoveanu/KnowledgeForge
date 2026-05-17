"""Helm chart container detector."""

import logging
from pathlib import Path
from typing import Any

import yaml

from .base_detector import BaseContainerDetector
from . import utils
from .relationship_extractor import EnvVarRelationshipExtractor

logger = logging.getLogger(__name__)


class HelmDetector(BaseContainerDetector):
    """Detect containers from Helm charts."""
    
    def __init__(self, repo_path: Path, llm_manager=None):
        """Initialize Helm detector.
        
        Args:
            repo_path: Path to repository root
            llm_manager: Optional LLM manager for descriptions
        """
        super().__init__(repo_path)
        self.llm_manager = llm_manager
    
    def can_detect(self) -> bool:
        """Check if Helm charts exist."""
        return bool(list(self.repo_path.rglob("Chart.yaml")))
    
    def detect(self) -> list[dict[str, Any]]:
        """Detect containers from Helm charts."""
        containers = []
        chart_files = list(self.repo_path.rglob("Chart.yaml"))
        
        for chart_file in chart_files:
            try:
                with open(chart_file) as f:
                    data = yaml.safe_load(f)

                # Helm "library" charts cannot be deployed standalone — they
                # only provide reusable templates to other charts. They are
                # not C4 containers; skip them upstream so they don't even
                # reach the LLM verdict pass.
                if isinstance(data, dict) and str(data.get("type") or "").lower() == "library":
                    logger.debug("Skipping Helm library chart at %s", chart_file)
                    continue

                chart_dir = chart_file.parent
                service_dir = chart_dir
                if chart_dir.name in {'chart', 'charts'} and chart_dir.parent != self.repo_path:
                    service_dir = chart_dir.parent

                chart_name = data.get('name', service_dir.name)
                rel_service_path = str(service_dir.relative_to(self.repo_path))

                container = {
                    "c4_level": 2,
                    "type": "container",
                    "name": chart_name,
                    "container_type": "Helm Deployed Service",
                    "technology": "Kubernetes",
                    "protocol": "HTTP",
                    "path": rel_service_path,
                    "runtime_environment": "Kubernetes",
                    "deployment": "Helm",
                    "description": data.get('description') or utils.extract_container_description(service_dir, self.llm_manager),

                    # IT Landscape fields
                    "repository_url": utils.get_repository_url(self.repo_path, service_dir),
                    "runtime_info": utils.extract_runtime_version(service_dir),
                    "dependencies_internal": [],
                    "health_endpoint": utils.extract_health_endpoint(service_dir),
                }

                # Set default description if still empty
                if not container.get("description"):
                    container["description"] = "Kubernetes workload deployed via Helm."

                # --- Relationship extraction ---
                relationships: list[dict] = []

                # 1. Chart.yaml subchart dependencies
                for dep in (data.get('dependencies') or []):
                    dep_name = dep.get('name') if isinstance(dep, dict) else str(dep)
                    if dep_name:
                        relationships.append({
                            "from": chart_name, "to": dep_name,
                            "type": "uses", "protocol": "HTTP",
                            "source": "helm",
                            "description": f"{chart_name} depends on Helm subchart {dep_name}",
                        })

                # 2. values.yaml: infer container type from image + scan for url/host/dsn/addr keys
                values_file = chart_dir / 'values.yaml'
                if values_file.exists():
                    try:
                        values_data = yaml.safe_load(
                            values_file.read_text(encoding='utf-8', errors='ignore')
                        ) or {}

                        # Look for image repository in values.yaml to refine container_type
                        image_from_values = self._extract_image_from_values(values_data)
                        if image_from_values:
                            inferred_type = utils.infer_type_from_image(image_from_values)
                            if inferred_type != "Service":
                                container["container_type"] = inferred_type
                            inferred_proto, _ = utils.infer_relationship_type_from_image(image_from_values)
                            if inferred_proto != "HTTP":
                                container["protocol"] = inferred_proto

                        for key, value in utils.flatten_dict(values_data):
                            key_lower = key.lower()
                            if any(h in key_lower for h in ('url', 'host', 'dsn', 'endpoint', 'addr', 'address')):
                                value_str = str(value).strip()
                                if value_str and value_str not in ('""', "''", 'null', '~', ''):
                                    if 'postgres' in key_lower or 'pg' in key_lower or '5432' in value_str:
                                        proto, port = 'PostgreSQL', '5432'
                                    elif 'redis' in key_lower or '6379' in value_str:
                                        proto, port = 'Redis', '6379'
                                    elif 'kafka' in key_lower or '9092' in value_str:
                                        proto, port = 'Kafka', '9092'
                                    elif 'grpc' in key_lower or '50051' in value_str:
                                        proto, port = 'gRPC', '50051'
                                    else:
                                        # Try to infer from image if available
                                        if image_from_values:
                                            proto, _ = utils.infer_relationship_type_from_image(image_from_values)
                                        else:
                                            proto = 'HTTP'
                                        port = ''
                                    relationships.append({
                                        "from": chart_name, "to": value_str,
                                        "type": "uses", "protocol": proto, "port": port,
                                        "source": "helm", "_unresolved": True,
                                        "description": f"{chart_name}.{key} → {value_str}",
                                    })
                    except Exception as e:
                        logger.debug(f"Error scanning values.yaml in {chart_dir}: {e}")

                # 3. Scan templates/ for Deployment/StatefulSet/DaemonSet → extract env var relationships
                templates_dir = chart_dir / 'templates'
                if templates_dir.exists():
                    for tpl_file in templates_dir.glob('*.yaml'):
                        try:
                            docs = list(yaml.safe_load_all(
                                tpl_file.read_text(encoding='utf-8', errors='ignore')
                            ))
                            for doc in docs:
                                if not isinstance(doc, dict):
                                    continue
                                if str(doc.get('kind', '')).lower() not in ('deployment', 'statefulset', 'daemonset'):
                                    continue
                                spec = (doc.get('spec') or {}).get('template', {}).get('spec', {})
                                for c_spec in (spec.get('containers') or []):
                                    img = c_spec.get('image', '')
                                    if img and container.get('container_type') == 'Helm Deployed Service':
                                        inferred = utils.infer_type_from_image(img)
                                        if inferred != "Service":
                                            container['container_type'] = inferred
                                    env_rels = EnvVarRelationshipExtractor(chart_name, 'helm').extract(
                                        c_spec.get('env') or []
                                    )
                                    relationships.extend(env_rels)
                        except Exception as e:
                            logger.debug(f"Error scanning template {tpl_file}: {e}")

                container["relationships"] = relationships
                containers.append(container)
            
            except Exception as e:
                logger.debug(f"Error parsing {chart_file}: {e}")

        return containers

    @staticmethod
    def _extract_image_from_values(values_data: dict) -> str:
        """Try to extract the primary service image name from values.yaml.

        Looks for common patterns:
        - image.repository: "my-image"
        - image: "my-image:tag"
        """
        if not isinstance(values_data, dict):
            return ""
        image_section = values_data.get('image')
        if isinstance(image_section, dict):
            repo = image_section.get('repository', '')
            if repo:
                return str(repo).strip()
        if isinstance(image_section, str) and image_section.strip():
            return image_section.split(':')[0].strip()
        return ""
