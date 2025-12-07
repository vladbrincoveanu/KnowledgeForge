"""Deployment topology extraction (Layer 3: Runtime/Deployment Architecture).

This analyzer extracts runtime and deployment architecture:
- Kubernetes deployments and their relationships
- Docker image → Deployment mappings
- Ingress → Service → Pod routing
- ConfigMaps/Secrets usage
- External service connections
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict

from domain.models.code_entities import (
    CodeEntity,
    CodeEntityType,
    CodeRelationship,
    ExtractionResult,
)

logger = logging.getLogger(__name__)


class DeploymentTopologyAnalyzer:
    """Analyze deployment topology from K8s manifests and Dockerfiles."""
    
    def __init__(self):
        """Initialize analyzer."""
        self.deployments: dict[str, dict[str, Any]] = {}
        self.services: dict[str, dict[str, Any]] = {}
        self.ingresses: dict[str, dict[str, Any]] = {}
        self.config_maps: dict[str, dict[str, Any]] = {}
        self.secrets: dict[str, dict[str, Any]] = {}
        self.pvcs: dict[str, dict[str, Any]] = {}
        self.namespaces: set[str] = set()
        self.docker_images: dict[str, dict[str, Any]] = {}
    
    def analyze(self, extraction_result: ExtractionResult) -> dict[str, Any]:
        """
        Analyze deployment topology.
        
        Returns:
            Complete deployment architecture
        """
        logger.info("Starting deployment topology analysis...")
        
        # Extract K8s resources
        self._extract_k8s_resources(extraction_result)
        
        # Map Docker images to deployments
        self._map_docker_to_deployments(extraction_result)
        
        # Build routing topology (Ingress → Service → Pod)
        routing = self._build_routing_topology()
        
        # Detect external services
        external_services = self._detect_external_services(extraction_result)
        
        # Build resource dependencies
        resource_deps = self._build_resource_dependencies()
        
        result = {
            "deployments": self.deployments,
            "services": self.services,
            "ingresses": self.ingresses,
            "config_maps": self.config_maps,
            "secrets": self.secrets,
            "pvcs": self.pvcs,
            "namespaces": list(self.namespaces),
            "docker_images": self.docker_images,
            "routing_topology": routing,
            "external_services": external_services,
            "resource_dependencies": resource_deps,
            "statistics": {
                "total_deployments": len(self.deployments),
                "total_services": len(self.services),
                "total_ingresses": len(self.ingresses),
                "total_namespaces": len(self.namespaces),
            }
        }
        
        logger.info(
            f"Found {len(self.deployments)} deployments, "
            f"{len(self.services)} services, "
            f"{len(self.ingresses)} ingresses"
        )
        
        return result
    
    def _extract_k8s_resources(self, result: ExtractionResult):
        """Extract Kubernetes resources from entities."""
        for entity in result.entities:
            if entity.source_type.value != "kubernetes":
                continue
            
            # Extract namespace
            if "namespace" in entity.attributes:
                self.namespaces.add(entity.attributes["namespace"])
            
            # Categorize by type
            if entity.entity_type == CodeEntityType.DEPLOYMENT:
                self._register_deployment(entity)
            elif entity.entity_type == CodeEntityType.SERVICE:
                self._register_service(entity)
            elif entity.entity_type == CodeEntityType.CONFIG_FILE:
                if "configmap" in entity.name.lower():
                    self._register_config_map(entity)
            elif entity.entity_type == CodeEntityType.SECRET:
                self._register_secret(entity)
            elif entity.entity_type == CodeEntityType.VOLUME:
                if "pvc" in entity.name.lower() or "claim" in entity.name.lower():
                    self._register_pvc(entity)
    
    def _register_deployment(self, entity: CodeEntity):
        """Register a deployment."""
        self.deployments[entity.id] = {
            "id": entity.id,
            "name": entity.name,
            "namespace": entity.attributes.get("namespace", "default"),
            "replicas": entity.attributes.get("replicas", 1),
            "image": entity.attributes.get("image"),
            "ports": entity.attributes.get("ports", []),
            "env_vars": entity.attributes.get("env_vars", []),
            "volumes": entity.attributes.get("volumes", []),
            "file": entity.file_path,
        }
    
    def _register_service(self, entity: CodeEntity):
        """Register a Kubernetes service."""
        self.services[entity.id] = {
            "id": entity.id,
            "name": entity.name,
            "namespace": entity.attributes.get("namespace", "default"),
            "type": entity.attributes.get("type", "ClusterIP"),
            "ports": entity.attributes.get("ports", []),
            "selector": entity.attributes.get("selector", {}),
            "file": entity.file_path,
        }
    
    def _register_config_map(self, entity: CodeEntity):
        """Register a ConfigMap."""
        self.config_maps[entity.id] = {
            "id": entity.id,
            "name": entity.name,
            "namespace": entity.attributes.get("namespace", "default"),
            "data": entity.attributes.get("data", {}),
            "file": entity.file_path,
        }
    
    def _register_secret(self, entity: CodeEntity):
        """Register a Secret."""
        self.secrets[entity.id] = {
            "id": entity.id,
            "name": entity.name,
            "namespace": entity.attributes.get("namespace", "default"),
            "type": entity.attributes.get("type", "Opaque"),
            "file": entity.file_path,
        }
    
    def _register_pvc(self, entity: CodeEntity):
        """Register a PVC."""
        self.pvcs[entity.id] = {
            "id": entity.id,
            "name": entity.name,
            "namespace": entity.attributes.get("namespace", "default"),
            "storage": entity.attributes.get("storage"),
            "file": entity.file_path,
        }
    
    def _map_docker_to_deployments(self, result: ExtractionResult):
        """Map Docker images to deployments."""
        # Extract Docker images
        for entity in result.entities:
            if entity.entity_type == CodeEntityType.CONTAINER:
                if entity.source_type.value == "docker":
                    self.docker_images[entity.id] = {
                        "id": entity.id,
                        "name": entity.name,
                        "base_images": entity.attributes.get("base_images", []),
                        "ports": entity.attributes.get("exposed_ports", []),
                        "file": entity.file_path,
                    }
        
        # Match images to deployments
        for dep_id, dep_info in self.deployments.items():
            if dep_info.get("image"):
                # Try to match with Dockerfile
                image_name = dep_info["image"].split(":")[0].split("/")[-1]
                
                for docker_id, docker_info in self.docker_images.items():
                    docker_name = docker_info["name"].lower()
                    if image_name.lower() in docker_name or docker_name in image_name.lower():
                        dep_info["dockerfile"] = docker_info["file"]
                        dep_info["dockerfile_id"] = docker_id
                        break
    
    def _build_routing_topology(self) -> list[dict[str, Any]]:
        """Build Ingress → Service → Deployment routing."""
        routes = []
        
        # For each ingress, find matching services
        for ingress_id, ingress_info in self.ingresses.items():
            for rule in ingress_info.get("rules", []):
                service_name = rule.get("service")
                
                # Find matching service
                for svc_id, svc_info in self.services.items():
                    if svc_info["name"] == service_name:
                        # Find matching deployments
                        selector = svc_info.get("selector", {})
                        
                        for dep_id, dep_info in self.deployments.items():
                            # Simple matching on name (can be improved)
                            if dep_info["name"] in service_name or service_name in dep_info["name"]:
                                routes.append({
                                    "ingress": ingress_info["name"],
                                    "ingress_path": rule.get("path", "/"),
                                    "service": svc_info["name"],
                                    "deployment": dep_info["name"],
                                    "namespace": dep_info["namespace"],
                                })
        
        return routes
    
    def _detect_external_services(self, result: ExtractionResult) -> list[dict[str, Any]]:
        """Detect external service dependencies."""
        external = []
        
        # Known external services in your infrastructure
        external_patterns = {
            "slurm": r"slurm|sbatch|squeue|scancel",
            "apptainer": r"apptainer|singularity",
            "harbor": r"harbor\..*|goharbor",
            "s3": r"s3\.|boto3|minio",
            "postgres": r"postgresql|psycopg",
            "redis": r"redis",
            "kafka": r"kafka",
            "clearml": r"clearml",
            "kubeflow": r"kubeflow|kfp",
        }
        
        # Search in code for external connections
        for entity in result.entities:
            if entity.entity_type in [CodeEntityType.FUNCTION, CodeEntityType.CLASS]:
                text = f"{entity.name} {entity.documentation or ''} {entity.signature or ''}"
                
                for ext_name, pattern in external_patterns.items():
                    if re.search(pattern, text, re.IGNORECASE):
                        external.append({
                            "type": ext_name,
                            "detected_in": entity.name,
                            "file": entity.file_path,
                        })
        
        # Deduplicate
        seen = set()
        unique_external = []
        for ext in external:
            key = (ext["type"], ext["file"])
            if key not in seen:
                seen.add(key)
                unique_external.append(ext)
        
        return unique_external
    
    def _build_resource_dependencies(self) -> dict[str, list[str]]:
        """Build resource dependency graph."""
        deps: dict[str, list[str]] = defaultdict(list)
        
        # Deployment → ConfigMap/Secret/PVC
        for dep_id, dep_info in self.deployments.items():
            dep_name = dep_info["name"]
            
            # Check env vars for ConfigMap/Secret refs
            for env_var in dep_info.get("env_vars", []):
                if isinstance(env_var, dict):
                    if "configMapRef" in env_var:
                        deps[dep_name].append(f"ConfigMap:{env_var['configMapRef']}")
                    if "secretRef" in env_var:
                        deps[dep_name].append(f"Secret:{env_var['secretRef']}")
            
            # Check volumes for PVC
            for volume in dep_info.get("volumes", []):
                if isinstance(volume, dict) and "pvc" in volume:
                    deps[dep_name].append(f"PVC:{volume['pvc']}")
        
        return dict(deps)
