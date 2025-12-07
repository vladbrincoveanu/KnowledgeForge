"""Service and bounded context detection (Layer 2: Application Architecture).

This analyzer groups code modules into logical services and identifies:
- Microservices and their boundaries
- Shared libraries vs services
- API endpoints exposed by services
- Service-to-service dependencies
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
    CodeRelationType,
    ExtractionResult,
)

logger = logging.getLogger(__name__)


class ServiceBoundaryDetector:
    """Detect service boundaries and group modules into services."""
    
    # Patterns that indicate a module is a service
    SERVICE_INDICATORS = [
        r".*_api$",
        r".*_service$",
        r".*_gateway$",
        r".*_worker$",
        r".*_daemon$",
    ]
    
    # Patterns for library/shared components
    LIBRARY_INDICATORS = [
        r".*/logger/.*",
        r".*/config/.*",
        r".*/utils/.*",
        r".*/common/.*",
        r".*/shared/.*",
        r".*/core/.*",
        r".*/models/.*",
    ]
    
    # Project structure patterns (monorepo)
    MONOREPO_PATTERNS = [
        r"projects/([^/]+)/",  # projects/service_name/
        r"services/([^/]+)/",  # services/service_name/
        r"apps/([^/]+)/",      # apps/app_name/
    ]
    
    def __init__(self, repo_path: Path):
        """Initialize detector."""
        self.repo_path = Path(repo_path)
        self.services: dict[str, dict[str, Any]] = {}
        self.libraries: dict[str, dict[str, Any]] = {}
        self.service_modules: dict[str, list[str]] = defaultdict(list)
    
    def analyze(self, extraction_result: ExtractionResult) -> dict[str, Any]:
        """
        Analyze extraction result and identify services.
        
        Returns:
            Dictionary with services, libraries, and groupings
        """
        logger.info("Starting service boundary detection...")
        
        # Group entities by file path
        entities_by_file: dict[str, list[CodeEntity]] = defaultdict(list)
        for entity in extraction_result.entities:
            entities_by_file[entity.file_path].append(entity)
        
        # Detect services from project structure
        self._detect_from_structure(extraction_result)
        
        # Detect services from API endpoints and main entry points
        self._detect_from_apis(extraction_result)
        
        # Classify libraries vs services
        self._classify_components(extraction_result)
        
        # Build service dependency graph
        dependencies = self._build_service_dependencies(extraction_result)
        
        result = {
            "services": self.services,
            "libraries": self.libraries,
            "service_modules": dict(self.service_modules),
            "service_dependencies": dependencies,
            "statistics": {
                "total_services": len(self.services),
                "total_libraries": len(self.libraries),
                "total_modules": len(entities_by_file),
            }
        }
        
        logger.info(
            f"Detected {len(self.services)} services and "
            f"{len(self.libraries)} libraries"
        )
        
        return result
    
    def _detect_from_structure(self, result: ExtractionResult):
        """Detect services from monorepo structure."""
        for entity in result.entities:
            file_path = entity.file_path
            
            # Check monorepo patterns
            for pattern in self.MONOREPO_PATTERNS:
                match = re.search(pattern, file_path)
                if match:
                    service_name = match.group(1)
                    self._register_service(service_name, file_path, "structure")
                    self.service_modules[service_name].append(entity.file_path)
                    break
    
    def _detect_from_apis(self, result: ExtractionResult):
        """Detect services from API definitions and main files."""
        for entity in result.entities:
            # FastAPI apps
            if entity.entity_type == CodeEntityType.MODULE:
                if any(
                    keyword in entity.file_path.lower()
                    for keyword in ["main.py", "app.py", "api.py", "server.py"]
                ):
                    service_name = self._infer_service_name(entity.file_path)
                    self._register_service(service_name, entity.file_path, "api_main")
            
            # Functions that look like API endpoints
            if entity.entity_type == CodeEntityType.FUNCTION:
                if entity.name in ["main", "create_app", "get_app"]:
                    service_name = self._infer_service_name(entity.file_path)
                    self._register_service(service_name, entity.file_path, "entry_point")
    
    def _classify_components(self, result: ExtractionResult):
        """Classify components as libraries or services."""
        for entity in result.entities:
            if entity.entity_type not in [CodeEntityType.MODULE, CodeEntityType.CLASS]:
                continue
            
            file_path = entity.file_path
            
            # Check if it's a library
            is_library = any(
                re.match(pattern, file_path)
                for pattern in self.LIBRARY_INDICATORS
            )
            
            if is_library:
                lib_name = self._infer_library_name(file_path)
                self._register_library(lib_name, file_path)
    
    def _register_service(self, name: str, file_path: str, source: str):
        """Register a detected service."""
        if name not in self.services:
            self.services[name] = {
                "name": name,
                "files": [],
                "detection_source": source,
                "type": "service",
            }
        
        if file_path not in self.services[name]["files"]:
            self.services[name]["files"].append(file_path)
    
    def _register_library(self, name: str, file_path: str):
        """Register a detected library."""
        if name not in self.libraries:
            self.libraries[name] = {
                "name": name,
                "files": [],
                "type": "library",
            }
        
        if file_path not in self.libraries[name]["files"]:
            self.libraries[name]["files"].append(file_path)
    
    def _infer_service_name(self, file_path: str) -> str:
        """Infer service name from file path."""
        parts = Path(file_path).parts
        
        # Look for projects/services/apps directory
        for i, part in enumerate(parts):
            if part in ["projects", "services", "apps"]:
                if i + 1 < len(parts):
                    return parts[i + 1]
        
        # Fallback: use parent directory
        if len(parts) > 1:
            return parts[-2]
        
        return "unknown_service"
    
    def _infer_library_name(self, file_path: str) -> str:
        """Infer library name from file path."""
        # Extract component name from path like "components/ai_factory/logger/..."
        match = re.search(r"components/([^/]+/[^/]+)", file_path)
        if match:
            return match.group(1).replace("/", "_")
        
        match = re.search(r"bases/([^/]+/[^/]+)", file_path)
        if match:
            return match.group(1).replace("/", "_")
        
        # Fallback
        parts = Path(file_path).parts
        if len(parts) > 2:
            return f"{parts[-3]}_{parts[-2]}"
        
        return "shared_library"
    
    def _build_service_dependencies(
        self, result: ExtractionResult
    ) -> dict[str, list[str]]:
        """Build service-to-service dependency graph."""
        dependencies: dict[str, list[str]] = defaultdict(list)
        
        # Map files to services
        file_to_service: dict[str, str] = {}
        for service_name, service_info in self.services.items():
            for file_path in service_info["files"]:
                file_to_service[file_path] = service_name
        
        # Analyze relationships
        for rel in result.relationships:
            if rel.relationship_type not in [
                CodeRelationType.IMPORTS,
                CodeRelationType.CALLS,
                CodeRelationType.DEPENDS_ON,
            ]:
                continue
            
            # Find source and target entities
            source_entity = next(
                (e for e in result.entities if e.id == rel.source_entity_id), None
            )
            target_entity = next(
                (e for e in result.entities if e.id == rel.target_entity_id), None
            )
            
            if not source_entity or not target_entity:
                continue
            
            # Map to services
            source_service = file_to_service.get(source_entity.file_path)
            target_service = file_to_service.get(target_entity.file_path)
            
            if source_service and target_service and source_service != target_service:
                if target_service not in dependencies[source_service]:
                    dependencies[source_service].append(target_service)
        
        return dict(dependencies)


class APIEndpointDetector:
    """Detect API endpoints and contracts."""
    
    # Patterns for FastAPI/Flask decorators
    FASTAPI_PATTERNS = [
        r"@router\.(get|post|put|delete|patch)\(['\"]([^'\"]+)",
        r"@app\.(get|post|put|delete|patch)\(['\"]([^'\"]+)",
    ]
    
    FLASK_PATTERNS = [
        r"@app\.route\(['\"]([^'\"]+)['\"].*methods=\[([^\]]+)\]",
        r"@blueprint\.route\(['\"]([^'\"]+)",
    ]
    
    def detect_endpoints(
        self, extraction_result: ExtractionResult
    ) -> list[dict[str, Any]]:
        """Detect API endpoints from code."""
        endpoints = []
        
        for entity in extraction_result.entities:
            if entity.entity_type != CodeEntityType.FUNCTION:
                continue
            
            # Check decorators in documentation or signature
            if entity.documentation:
                endpoints.extend(
                    self._parse_decorators(
                        entity.documentation, entity.name, entity.file_path
                    )
                )
            
            if entity.signature:
                endpoints.extend(
                    self._parse_decorators(
                        entity.signature, entity.name, entity.file_path
                    )
                )
        
        return endpoints
    
    def _parse_decorators(
        self, text: str, function_name: str, file_path: str
    ) -> list[dict[str, Any]]:
        """Parse API decorators from text."""
        endpoints = []
        
        for pattern in self.FASTAPI_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                endpoints.append({
                    "path": match.group(2),
                    "method": match.group(1).upper(),
                    "function": function_name,
                    "file": file_path,
                    "framework": "fastapi",
                })
        
        for pattern in self.FLASK_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                endpoints.append({
                    "path": match.group(1),
                    "function": function_name,
                    "file": file_path,
                    "framework": "flask",
                })
        
        return endpoints
