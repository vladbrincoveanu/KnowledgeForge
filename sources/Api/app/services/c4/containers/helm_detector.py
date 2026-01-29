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
                
                containers.append(container)
            
            except Exception as e:
                logger.debug(f"Error parsing {chart_file}: {e}")
        
        return containers
