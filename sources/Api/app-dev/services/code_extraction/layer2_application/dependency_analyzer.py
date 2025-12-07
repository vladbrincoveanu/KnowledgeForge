"""Service dependency analyzer for Layer 2.

Analyzes:
- Helm values → external service URLs
- K8s Services → Ingress routing
- Code imports → library dependencies
- GitOps applications → deployment dependencies
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict

import yaml

from domain.models.code_entities import ExtractionResult, CodeEntity

logger = logging.getLogger(__name__)


class ServiceDependencyAnalyzer:
    """Extract service dependencies from multiple sources."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path)
        
    def analyze(self, base_extraction: ExtractionResult) -> dict[str, Any]:
        """Analyze service dependencies across the codebase."""
        
        dependencies = {
            "external_services": self._extract_external_services(),
            "internal_routes": self._extract_internal_routes(),
            "code_dependencies": self._extract_code_dependencies(base_extraction),
            "deployment_dependencies": self._extract_deployment_dependencies(),
        }
        
        # Build dependency graph
        dependency_graph = self._build_dependency_graph(dependencies)
        
        return {
            "external_services": dependencies["external_services"],
            "internal_routes": dependencies["internal_routes"],
            "code_dependencies": dependencies["code_dependencies"],
            "deployment_dependencies": dependencies["deployment_dependencies"],
            "dependency_graph": dependency_graph,
            "statistics": {
                "total_external_services": len(dependencies["external_services"]),
                "total_internal_routes": len(dependencies["internal_routes"]),
                "total_code_dependencies": len(dependencies["code_dependencies"]),
                "total_deployment_deps": len(dependencies["deployment_dependencies"]),
            }
        }
    
    def _extract_external_services(self) -> list[dict[str, Any]]:
        """Extract external service URLs from Helm values."""
        external_services = []
        
        # Find all values.yaml files
        values_files = list(self.repo_path.glob("**/values.yaml"))
        
        for values_file in values_files:
            try:
                with open(values_file) as f:
                    values = yaml.safe_load(f)
                
                if not values:
                    continue
                
                # Extract external URLs and service configurations
                service_name = values_file.parent.parent.name
                
                # Common patterns for external services
                external = self._extract_from_values(values, service_name, values_file)
                external_services.extend(external)
                
            except Exception as e:
                logger.debug(f"Error parsing {values_file}: {e}")
                continue
        
        return external_services
    
    def _extract_from_values(
        self, 
        values: dict[str, Any], 
        service_name: str,
        file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract external service references from values dict."""
        external = []
        
        # Look for common external service patterns
        patterns = {
            "externalURL": "external_url",
            "host": "host",
            "endpoint": "endpoint",
            "url": "url",
            "apiURL": "api_url",
            "baseURL": "base_url",
        }
        
        def recursive_search(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    # Check if this looks like an external service
                    if isinstance(value, str):
                        # URL pattern
                        if any(proto in value for proto in ["http://", "https://", "://"]):
                            external.append({
                                "source_service": service_name,
                                "type": patterns.get(key, "unknown"),
                                "url": value,
                                "config_path": current_path,
                                "file": str(file_path.relative_to(self.repo_path)),
                            })
                        # Host pattern (without protocol)
                        elif key in patterns and "." in value:
                            external.append({
                                "source_service": service_name,
                                "type": patterns[key],
                                "url": value,
                                "config_path": current_path,
                                "file": str(file_path.relative_to(self.repo_path)),
                            })
                    
                    # Recurse into nested dicts
                    recursive_search(value, current_path)
            
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    recursive_search(item, f"{path}[{idx}]")
        
        recursive_search(values)
        return external
    
    def _extract_internal_routes(self) -> list[dict[str, Any]]:
        """Extract K8s Service to Ingress routing."""
        routes = []
        
        # Find all K8s manifests
        yaml_files = list(self.repo_path.glob("**/*.yaml"))
        
        ingresses = {}
        services = {}
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file) as f:
                    docs = list(yaml.safe_load_all(f))
                
                for doc in docs:
                    if not doc or not isinstance(doc, dict):
                        continue
                    
                    kind = doc.get("kind")
                    
                    if kind == "Ingress":
                        ingress_name = doc.get("metadata", {}).get("name")
                        if ingress_name:
                            ingresses[ingress_name] = {
                                "name": ingress_name,
                                "rules": doc.get("spec", {}).get("rules", []),
                                "file": str(yaml_file.relative_to(self.repo_path)),
                            }
                    
                    elif kind == "Service":
                        svc_name = doc.get("metadata", {}).get("name")
                        if svc_name:
                            services[svc_name] = {
                                "name": svc_name,
                                "type": doc.get("spec", {}).get("type", "ClusterIP"),
                                "ports": doc.get("spec", {}).get("ports", []),
                                "file": str(yaml_file.relative_to(self.repo_path)),
                            }
            
            except Exception as e:
                logger.debug(f"Error parsing {yaml_file}: {e}")
                continue
        
        # Map Ingress rules to Services
        for ingress_name, ingress in ingresses.items():
            for rule in ingress.get("rules", []):
                host = rule.get("host")
                http = rule.get("http", {})
                
                for path_rule in http.get("paths", []):
                    backend = path_rule.get("backend", {})
                    service_name = backend.get("service", {}).get("name")
                    service_port = backend.get("service", {}).get("port", {})
                    
                    if service_name:
                        routes.append({
                            "ingress": ingress_name,
                            "host": host,
                            "path": path_rule.get("path", "/"),
                            "service": service_name,
                            "port": service_port.get("number") or service_port.get("name"),
                            "type": "http_routing",
                        })
        
        return routes
    
    def _extract_code_dependencies(
        self, 
        base_extraction: ExtractionResult
    ) -> list[dict[str, Any]]:
        """Extract code-level dependencies from import relationships."""
        code_deps = []
        
        # Group entities by file/module
        modules = defaultdict(set)
        for entity in base_extraction.entities:
            if entity.entity_type.value == "module":
                modules[entity.name].add(entity.file_path)
        
        # Find import relationships
        for rel in base_extraction.relationships:
            if rel.relationship_type.value == "imports":
                # Find source and target entities
                source = next(
                    (e for e in base_extraction.entities if e.id == rel.source_entity_id),
                    None
                )
                target = next(
                    (e for e in base_extraction.entities if e.id == rel.target_entity_id),
                    None
                )
                
                if source and target:
                    code_deps.append({
                        "from_module": source.name,
                        "from_file": source.file_path,
                        "to_module": target.name,
                        "to_file": target.file_path,
                        "type": "code_import",
                    })
        
        return code_deps
    
    def _extract_deployment_dependencies(self) -> list[dict[str, Any]]:
        """Extract deployment dependencies from GitOps applications."""
        deps = []
        
        # Find ArgoCD Application manifests
        gitops_files = list(self.repo_path.glob("gitops/**/*.yaml"))
        
        for gitops_file in gitops_files:
            try:
                with open(gitops_file) as f:
                    docs = list(yaml.safe_load_all(f))
                
                for doc in docs:
                    if not doc or not isinstance(doc, dict):
                        continue
                    
                    if doc.get("kind") == "Application":
                        app_name = doc.get("metadata", {}).get("name")
                        sync_wave = doc.get("metadata", {}).get("annotations", {}).get(
                            "argocd.argoproj.io/sync-wave", "0"
                        )
                        
                        deps.append({
                            "application": app_name,
                            "sync_wave": int(sync_wave) if sync_wave.lstrip("-").isdigit() else 0,
                            "namespace": doc.get("spec", {}).get("destination", {}).get("namespace"),
                            "source_path": doc.get("spec", {}).get("source", {}).get("path"),
                            "type": "argocd_app",
                        })
            
            except Exception as e:
                logger.debug(f"Error parsing {gitops_file}: {e}")
                continue
        
        # Sort by sync wave (deployment order)
        deps.sort(key=lambda x: x["sync_wave"])
        
        return deps
    
    def _build_dependency_graph(self, dependencies: dict[str, Any]) -> dict[str, Any]:
        """Build a unified dependency graph from all sources."""
        graph = {
            "nodes": [],
            "edges": [],
        }
        
        # Add service nodes from external services
        service_nodes = set()
        for ext_svc in dependencies["external_services"]:
            source = ext_svc["source_service"]
            if source not in service_nodes:
                graph["nodes"].append({
                    "id": source,
                    "type": "internal_service",
                    "label": source,
                })
                service_nodes.add(source)
            
            # Add external service as node
            target = ext_svc["url"]
            if target not in service_nodes:
                graph["nodes"].append({
                    "id": target,
                    "type": "external_service",
                    "label": target,
                })
                service_nodes.add(target)
            
            # Add edge
            graph["edges"].append({
                "from": source,
                "to": target,
                "type": ext_svc["type"],
                "label": ext_svc["config_path"],
            })
        
        # Add routing edges
        for route in dependencies["internal_routes"]:
            if route["service"] not in service_nodes:
                graph["nodes"].append({
                    "id": route["service"],
                    "type": "k8s_service",
                    "label": route["service"],
                })
                service_nodes.add(route["service"])
            
            graph["edges"].append({
                "from": route["host"] or "ingress",
                "to": route["service"],
                "type": "http_route",
                "label": route["path"],
            })
        
        return graph
