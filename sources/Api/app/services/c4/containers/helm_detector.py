"""Helm chart container detector."""

import logging
from pathlib import Path
from typing import Any

import yaml

from .base_detector import BaseContainerDetector
from . import utils

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

                # 2. values.yaml: scan for url/host/dsn/addr keys → infer protocol
                values_file = chart_dir / 'values.yaml'
                if values_file.exists():
                    try:
                        values_data = yaml.safe_load(
                            values_file.read_text(encoding='utf-8', errors='ignore')
                        ) or {}
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
                                        proto, port = 'HTTP', ''
                                    relationships.append({
                                        "from": chart_name, "to": value_str,
                                        "type": "uses", "protocol": proto, "port": port,
                                        "source": "helm", "_unresolved": True,
                                        "description": f"{chart_name}.{key} → {value_str}",
                                    })
                    except Exception as e:
                        logger.debug(f"Error scanning values.yaml in {chart_dir}: {e}")

                container["relationships"] = relationships
                containers.append(container)
            
            except Exception as e:
                logger.debug(f"Error parsing {chart_file}: {e}")
        
        return containers
