"""Docker Compose container detector."""

import logging
from pathlib import Path
from typing import Any

import yaml

from .base_detector import BaseContainerDetector
from . import utils

logger = logging.getLogger(__name__)


class ComposeDetector(BaseContainerDetector):
    """Detect containers from docker-compose files."""
    
    def __init__(self, repo_path: Path):
        """Initialize compose detector."""
        super().__init__(repo_path)
    
    def can_detect(self) -> bool:
        """Check if docker-compose files exist."""
        compose_patterns = ["docker-compose*.yaml", "docker-compose*.yml"]
        for pattern in compose_patterns:
            if list(self.repo_path.rglob(pattern)):
                return True
        return False
    
    def detect(self) -> list[dict[str, Any]]:
        """Detect containers from docker-compose files."""
        containers = []
        compose_files = list(self.repo_path.rglob("docker-compose*.yaml")) + \
                       list(self.repo_path.rglob("docker-compose*.yml"))
        
        for compose_file in compose_files:
            try:
                with open(compose_file) as f:
                    data = yaml.safe_load(f)
                
                services = data.get('services', {})
                
                for service_name, service_config in services.items():
                    # Extract runtime from image
                    image = service_config.get('image', '')
                    runtime = utils.extract_runtime_from_image(image)
                    
                    container = {
                        "c4_level": 2,
                        "type": "container",
                        "name": service_name,
                        "container_type": utils.infer_type_from_image(image),
                        "technology": image.split(':')[0] if image else "Unknown",
                        "protocol": "HTTP",
                        "path": str(compose_file.relative_to(self.repo_path)),
                        
                        # IT Landscape fields
                        "repository_url": utils.get_repository_url(self.repo_path, compose_file.parent),
                        "runtime_info": runtime,
                        "dependencies_internal": service_config.get('depends_on', []) if isinstance(service_config.get('depends_on'), list) else [],
                        "health_endpoint": utils.extract_health_from_compose(service_config),
                    }
                    
                    containers.append(container)
            
            except Exception as e:
                logger.debug(f"Error parsing {compose_file}: {e}")
        
        return containers
