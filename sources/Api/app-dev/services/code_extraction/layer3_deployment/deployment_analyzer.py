"""Deployment topology extraction (Layer 3: Runtime/Deployment Architecture).

This analyzer extracts runtime and deployment architecture from multiple sources:
- Helm chart templates (structure, not values)
- ArgoCD/GitOps manifests (deployment order, sync waves)
- Kustomize overlays
- Raw Kubernetes manifests
- Docker Compose files
- Terraform/IaC deployment configs

Generic approach: detect what exists and extract accordingly.
"""

import logging
import re
import yaml
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
    """Analyze deployment topology from multiple deployment tool sources."""
    
    def __init__(self, repo_path: Path):
        """Initialize analyzer."""
        self.repo_path = Path(repo_path)
        self.deployments: dict[str, dict[str, Any]] = {}
        self.services: dict[str, dict[str, Any]] = {}
        self.ingresses: dict[str, dict[str, Any]] = {}
        self.config_maps: dict[str, dict[str, Any]] = {}
        self.secrets: dict[str, dict[str, Any]] = {}
        self.pvcs: dict[str, dict[str, Any]] = {}
        self.namespaces: set[str] = set()
        self.docker_images: dict[str, dict[str, Any]] = {}
        self.helm_charts: dict[str, dict[str, Any]] = {}
        self.deployment_tools: set[str] = set()
    
    def analyze(self, extraction_result: ExtractionResult) -> dict[str, Any]:
        """
        Analyze deployment topology from available sources.
        
        Auto-detects deployment tooling and extracts accordingly:
        - Helm charts → structure extraction
        - ArgoCD → deployment order
        - Kustomize → overlays
        - Raw K8s → manifests
        - Docker Compose → service definitions
        
        Returns:
            Complete deployment architecture
        """
        logger.info("Starting deployment topology analysis...")
        
        # Detect deployment tools used
        self._detect_deployment_tools()
        
        # Extract from Helm charts (if present)
        if "helm" in self.deployment_tools:
            self._extract_helm_charts()
        
        # Extract from ArgoCD (if present)
        if "argocd" in self.deployment_tools or "gitops" in self.deployment_tools:
            self._extract_argocd_apps()
        
        # Extract from Kustomize (if present)
        if "kustomize" in self.deployment_tools:
            self._extract_kustomize()
        
        # Extract from Docker Compose (if present)
        if "docker-compose" in self.deployment_tools:
            self._extract_docker_compose()
        
        # Extract K8s resources from code entities (fallback)
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
            "deployment_tools": list(self.deployment_tools),
            "helm_charts": self.helm_charts,
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
                "total_deployment_tools": len(self.deployment_tools),
                "total_helm_charts": len(self.helm_charts),
                "total_deployments": len(self.deployments),
                "total_services": len(self.services),
                "total_ingresses": len(self.ingresses),
                "total_namespaces": len(self.namespaces),
            }
        }
        
        logger.info(
            f"Found {len(self.deployment_tools)} deployment tools: {', '.join(self.deployment_tools)}"
        )
        logger.info(
            f"Found {len(self.helm_charts)} Helm charts, "
            f"{len(self.deployments)} deployments, "
            f"{len(self.services)} services, "
            f"{len(self.ingresses)} ingresses"
        )
        
        return result
    
    def _detect_deployment_tools(self):
        """Auto-detect which deployment tools are in use."""
        # Check for Helm
        if list(self.repo_path.rglob("Chart.yaml")):
            self.deployment_tools.add("helm")
        
        # Check for ArgoCD/GitOps
        if list(self.repo_path.rglob("**/gitops/**/*.yaml")) or \
           list(self.repo_path.rglob("**/argocd/**/*.yaml")):
            self.deployment_tools.add("argocd")
            self.deployment_tools.add("gitops")
        
        # Check for Kustomize
        if list(self.repo_path.rglob("kustomization.yaml")):
            self.deployment_tools.add("kustomize")
        
        # Check for Docker Compose
        if list(self.repo_path.rglob("docker-compose*.yaml")) or \
           list(self.repo_path.rglob("docker-compose*.yml")):
            self.deployment_tools.add("docker-compose")
        
        # Check for Terraform/IaC K8s
        tf_files = list(self.repo_path.rglob("*.tf"))
        if tf_files:
            for tf_file in tf_files[:10]:  # Sample check
                try:
                    content = tf_file.read_text()
                    if "kubernetes_" in content or "helm_release" in content:
                        self.deployment_tools.add("terraform")
                        break
                except Exception:
                    continue
        
        logger.info(f"Detected deployment tools: {self.deployment_tools}")
    
    def _extract_helm_charts(self):
        """Extract structure from Helm charts."""
        chart_files = list(self.repo_path.rglob("Chart.yaml"))
        
        for chart_file in chart_files:
            try:
                with open(chart_file) as f:
                    chart_data = yaml.safe_load(f)
                
                chart_name = chart_data.get("name", chart_file.parent.name)
                chart_dir = chart_file.parent
                
                # Find templates
                templates_dir = chart_dir / "templates"
                templates = []
                resources = defaultdict(list)
                
                if templates_dir.exists():
                    for template_file in templates_dir.glob("*.yaml"):
                        templates.append(str(template_file.relative_to(self.repo_path)))
                        
                        # Try to extract resource type from template
                        try:
                            content = template_file.read_text()
                            # Look for "kind:" even in templates
                            kind_match = re.search(r'^kind:\s*(\w+)', content, re.MULTILINE)
                            if kind_match:
                                kind = kind_match.group(1)
                                resources[kind].append(template_file.name)
                                
                                # Register as deployment resource
                                if kind in ["Deployment", "StatefulSet", "DaemonSet"]:
                                    self._register_helm_deployment(chart_name, template_file, kind)
                                elif kind == "Service":
                                    self._register_helm_service(chart_name, template_file)
                                elif kind == "Ingress":
                                    self._register_helm_ingress(chart_name, template_file)
                        except Exception as e:
                            logger.debug(f"Could not parse template {template_file}: {e}")
                
                self.helm_charts[chart_name] = {
                    "name": chart_name,
                    "version": chart_data.get("version", "unknown"),
                    "description": chart_data.get("description", ""),
                    "chart_file": str(chart_file.relative_to(self.repo_path)),
                    "templates": templates,
                    "resources": dict(resources),
                    "values_file": str((chart_dir / "values.yaml").relative_to(self.repo_path)) 
                                   if (chart_dir / "values.yaml").exists() else None,
                }
                
            except Exception as e:
                logger.warning(f"Error processing Helm chart {chart_file}: {e}")
    
    def _register_helm_deployment(self, chart_name: str, template_file: Path, kind: str):
        """Register a deployment from Helm template."""
        deployment_id = f"helm_{chart_name}_{template_file.stem}"
        self.deployments[deployment_id] = {
            "id": deployment_id,
            "name": template_file.stem,
            "chart": chart_name,
            "kind": kind,
            "template": str(template_file.relative_to(self.repo_path)),
            "source": "helm",
        }
    
    def _register_helm_service(self, chart_name: str, template_file: Path):
        """Register a service from Helm template."""
        service_id = f"helm_{chart_name}_{template_file.stem}"
        self.services[service_id] = {
            "id": service_id,
            "name": template_file.stem,
            "chart": chart_name,
            "template": str(template_file.relative_to(self.repo_path)),
            "source": "helm",
        }
    
    def _register_helm_ingress(self, chart_name: str, template_file: Path):
        """Register an ingress from Helm template."""
        ingress_id = f"helm_{chart_name}_{template_file.stem}"
        self.ingresses[ingress_id] = {
            "id": ingress_id,
            "name": template_file.stem,
            "chart": chart_name,
            "template": str(template_file.relative_to(self.repo_path)),
            "source": "helm",
        }
    
    def _extract_argocd_apps(self):
        """Extract ArgoCD application manifests."""
        # This would parse gitops/**/*.yaml files
        # Already handled by ServiceDependencyAnalyzer in Layer 2
        # Could move here if it fits better
        pass
    
    def _extract_kustomize(self):
        """Extract Kustomize overlays."""
        kustomize_files = list(self.repo_path.rglob("kustomization.yaml"))
        
        for kust_file in kustomize_files:
            try:
                with open(kust_file) as f:
                    kust_data = yaml.safe_load(f)
                
                # Track kustomize bases and overlays
                # Could extract resources, patches, etc.
                logger.debug(f"Found kustomize: {kust_file}")
            except Exception as e:
                logger.debug(f"Error parsing kustomize {kust_file}: {e}")
    
    def _extract_docker_compose(self):
        """Extract Docker Compose service definitions."""
        compose_files = list(self.repo_path.rglob("docker-compose*.yaml")) + \
                       list(self.repo_path.rglob("docker-compose*.yml"))
        
        for compose_file in compose_files:
            try:
                with open(compose_file) as f:
                    compose_data = yaml.safe_load(f)
                
                services = compose_data.get("services", {})
                for service_name, service_config in services.items():
                    self._register_compose_service(service_name, service_config, compose_file)
            except Exception as e:
                logger.warning(f"Error parsing docker-compose {compose_file}: {e}")
    
    def _register_compose_service(self, name: str, config: dict, compose_file: Path):
        """Register a Docker Compose service."""
        service_id = f"compose_{name}"
        self.deployments[service_id] = {
            "id": service_id,
            "name": name,
            "image": config.get("image"),
            "ports": config.get("ports", []),
            "environment": config.get("environment", []),
            "volumes": config.get("volumes", []),
            "file": str(compose_file.relative_to(self.repo_path)),
            "source": "docker-compose",
        }
    
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
