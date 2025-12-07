"""API endpoint extractor for Layer 2.

Extracts REST API endpoints by reading source code and parsing decorators.
"""

import logging
import re
from pathlib import Path
from typing import Any

from domain.models.code_entities import ExtractionResult, CodeEntityType

logger = logging.getLogger(__name__)


class APIEndpointDetector:
    """Detect API endpoints by parsing source code decorators."""
    
    # FastAPI decorator patterns
    FASTAPI_DECORATOR_PATTERNS = [
        r'@(?:app|api|router)\.(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']',
    ]
    
    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path)
    
    def detect_endpoints(self, extraction_result: ExtractionResult) -> list[dict[str, Any]]:
        """Detect API endpoints from extracted functions."""
        endpoints = []
        
        # Group functions by file
        functions_by_file = {}
        for entity in extraction_result.entities:
            if entity.entity_type == CodeEntityType.FUNCTION:
                file_path = entity.file_path
                if file_path not in functions_by_file:
                    functions_by_file[file_path] = []
                functions_by_file[file_path].append(entity)
        
        # Process each file
        for file_path, functions in functions_by_file.items():
            full_path = self.repo_path / file_path
            
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r') as f:
                    source_lines = f.readlines()
                
                # Extract endpoints from each function
                for func in functions:
                    endpoint_info = self._extract_endpoint_from_function(
                        func, source_lines, file_path
                    )
                    if endpoint_info:
                        endpoints.append(endpoint_info)
            
            except Exception as e:
                logger.debug(f"Error reading {full_path}: {e}")
                continue
        
        logger.info(f"Detected {len(endpoints)} API endpoints")
        return endpoints
    
    def _extract_endpoint_from_function(
        self,
        func_entity: Any,
        source_lines: list[str],
        file_path: str
    ) -> dict[str, Any] | None:
        """Extract API endpoint info from a function and its decorators."""
        
        if func_entity.line_start is None:
            return None
        
        # Look at lines before the function definition for decorators
        start_line = max(0, func_entity.line_start - 10)  # Look up to 10 lines before
        end_line = func_entity.line_start
        
        decorator_text = ''.join(source_lines[start_line:end_line])
        
        # Check for FastAPI decorators
        for pattern in self.FASTAPI_DECORATOR_PATTERNS:
            match = re.search(pattern, decorator_text, re.MULTILINE)
            if match:
                method = match.group(1).upper()
                path = match.group(2)
                
                # Extract function docstring for description
                description = self._extract_docstring(func_entity, source_lines)
                
                # Extract parameters from signature
                parameters = self._extract_parameters_from_signature(func_entity.signature)
                
                return {
                    "path": path,
                    "method": method,
                    "function": func_entity.name,
                    "file": file_path,
                    "framework": "fastapi",
                    "description": description,
                    "parameters": parameters,
                    "line": func_entity.line_start,
                }
        
        return None
    
    def _extract_docstring(self, func_entity: Any, source_lines: list[str]) -> str | None:
        """Extract docstring from function."""
        if func_entity.line_start is None or func_entity.line_end is None:
            return None
        
        # Look for docstring in first few lines after function def
        start = func_entity.line_start
        end = min(func_entity.line_start + 20, func_entity.line_end, len(source_lines))
        
        func_text = ''.join(source_lines[start:end])
        
        # Match triple-quoted docstrings
        docstring_match = re.search(r'"""(.+?)"""', func_text, re.DOTALL)
        if docstring_match:
            # Get first line only for summary
            docstring = docstring_match.group(1).strip()
            first_line = docstring.split('\n')[0].strip()
            return first_line
        
        return None
    
    def _extract_parameters_from_signature(self, signature: str | None) -> list[dict[str, str]]:
        """Extract parameter names and types from function signature."""
        if not signature:
            return []
        
        parameters = []
        
        # Simple extraction - could be enhanced
        # Match parameter patterns like "param_name: Type"
        param_pattern = r'(\w+):\s*([^,=\)]+)'
        matches = re.findall(param_pattern, signature)
        
        for name, param_type in matches:
            # Skip common dependency injection params
            if name in ['self', 'cls']:
                continue
            
            parameters.append({
                "name": name,
                "type": param_type.strip(),
            })
        
        return parameters
