"""Docker Compose container detector."""

import logging
from pathlib import Path
from typing import Any

import yaml

from .base_detector import BaseContainerDetector
from . import utils
from .relationship_extractor import EnvVarRelationshipExtractor

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
            if list(self.repo_path.glob(pattern)):
                return True
        return False
    
    def detect(self) -> list[dict[str, Any]]:
        """Detect containers from docker-compose files."""
        containers = []
        compose_files = list(self.repo_path.glob("docker-compose*.yaml")) + \
                       list(self.repo_path.glob("docker-compose*.yml"))

        for compose_file in compose_files:
            try:
                with open(compose_file) as f:
                    data = yaml.safe_load(f)

                services = data.get('services', {})
                file_containers = []

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
                        "protocol": self._infer_service_protocol(image, service_config),
                        "path": str(compose_file.relative_to(self.repo_path)),

                        # IT Landscape fields
                        "repository_url": utils.get_repository_url(self.repo_path, compose_file.parent),
                        "runtime_info": runtime,
                        "dependencies_internal": utils.normalize_depends_on(service_config.get('depends_on', {})),
                        "health_endpoint": utils.extract_health_from_compose(service_config),
                    }

                    file_containers.append(container)

                # --- Relationship extraction ---
                relationships: list[dict] = []
                volume_users: dict[str, list[str]] = {}

                for service_name, service_config in services.items():
                    # depends_on (normalized) — infer protocol from target service's image
                    for dep in utils.normalize_depends_on(service_config.get('depends_on', {})):
                        if dep in services and dep != service_name:
                            dep_image = services[dep].get('image', '')
                            dep_protocol, dep_rel_type = utils.infer_relationship_type_from_image(dep_image)
                            relationships.append({
                                "from": service_name, "to": dep,
                                "type": dep_rel_type, "protocol": dep_protocol,
                                "source": "compose",
                                "description": f"{service_name} depends on {dep}",
                            })

                    # links (may include alias: "service:alias")
                    for link in service_config.get('links', []):
                        target = link.split(':')[0]
                        if target in services and target != service_name:
                            target_image = services[target].get('image', '')
                            link_protocol, link_rel_type = utils.infer_relationship_type_from_image(target_image)
                            relationships.append({
                                "from": service_name, "to": target,
                                "type": link_rel_type, "protocol": link_protocol,
                                "source": "compose",
                                "description": f"{service_name} links to {target}",
                            })

                    # environment variables → EnvVarRelationshipExtractor
                    env = service_config.get('environment', {})
                    if env:
                        if isinstance(env, dict):
                            env_rels = EnvVarRelationshipExtractor(service_name, "compose").extract_from_dict(env)
                        elif isinstance(env, list):
                            env_dict = {}
                            for item in env:
                                if isinstance(item, str) and '=' in item:
                                    k, _, v = item.partition('=')
                                    env_dict[k.strip()] = v.strip()
                            env_rels = EnvVarRelationshipExtractor(service_name, "compose").extract_from_dict(env_dict)
                        else:
                            env_rels = []
                        relationships.extend(env_rels)

                    # named volumes (collect for second pass)
                    for vol in service_config.get('volumes', []):
                        vol_str = vol if isinstance(vol, str) else str(vol)
                        vol_name = utils.extract_named_volume(vol_str)
                        if vol_name:
                            volume_users.setdefault(vol_name, []).append(service_name)

                # shares-volume relationships
                for vol_name, users in volume_users.items():
                    if len(users) > 1:
                        for i, a in enumerate(users):
                            for b in users[i + 1:]:
                                relationships.append({
                                    "from": a, "to": b,
                                    "type": "shares-volume", "protocol": "filesystem",
                                    "source": "compose",
                                    "description": f"Shared volume: {vol_name}",
                                })

                # Attach relationships to each container dict
                for container in file_containers:
                    container["relationships"] = [
                        r for r in relationships if r["from"] == container["name"]
                    ]

                containers.extend(file_containers)

            except Exception as e:
                logger.debug(f"Error parsing {compose_file}: {e}")

        return containers

    @staticmethod
    def _infer_service_protocol(image: str, service_config: dict) -> str:
        """Infer the primary protocol for a compose service.

        Priority:
        1. Event-bus images (Kafka, RabbitMQ, etc.) via infer_relationship_type_from_image
        2. Well-known database/cache images via infer_type_from_image
        3. Exposed port numbers via infer_protocol_from_port
        4. Default HTTP
        """
        # Event-bus / broker images
        proto, _ = utils.infer_relationship_type_from_image(image)
        if proto != "HTTP":
            return proto

        # Database / cache images from type name
        container_type = utils.infer_type_from_image(image)
        for keyword, protocol in (
            ("PostgreSQL", "PostgreSQL"),
            ("MongoDB", "MongoDB"),
            ("Redis", "Redis"),
            ("SQL Server", "SQLServer"),
            ("Elasticsearch", "Elasticsearch"),
            ("Search", "Elasticsearch"),
        ):
            if keyword in container_type:
                return protocol

        # Exposed ports
        for port_spec in service_config.get('ports', []):
            port_str = str(port_spec).split(':')[-1].split('/')[0]
            inferred = utils.infer_protocol_from_port(port_str)
            if inferred != "TCP":
                return inferred

        return "HTTP"
