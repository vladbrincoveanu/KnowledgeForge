"""Data flow and workflow extraction (Layer 4: Data & Workflow Architecture).

This analyzer extracts data and workflow architecture:
- Data flow between functions/services
- Input/output schemas
- Workflow steps and sequences
- Artifacts and transformations
- External system interactions
"""

import logging
import re
import ast
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


class DataFlowAnalyzer:
    """Analyze data flow and transformations."""
    
    def __init__(self):
        """Initialize analyzer."""
        self.workflows: dict[str, dict[str, Any]] = {}
        self.data_flows: list[dict[str, Any]] = []
        self.schemas: dict[str, dict[str, Any]] = {}
        self.artifacts: list[dict[str, Any]] = []
    
    def analyze(self, extraction_result: ExtractionResult) -> dict[str, Any]:
        """
        Analyze data flows and workflows.
        
        Returns:
            Complete data/workflow architecture
        """
        logger.info("Starting data flow analysis...")
        
        # Detect workflows (Kubeflow, ClearML, custom)
        self._detect_workflows(extraction_result)
        
        # Extract function I/O signatures
        io_signatures = self._extract_io_signatures(extraction_result)
        
        # Build data flow graph
        self._build_data_flows(extraction_result, io_signatures)
        
        # Detect Pydantic models and schemas
        self._detect_schemas(extraction_result)
        
        # Detect file/artifact operations
        self._detect_artifacts(extraction_result)
        
        result = {
            "workflows": self.workflows,
            "data_flows": self.data_flows,
            "schemas": self.schemas,
            "artifacts": self.artifacts,
            "io_signatures": io_signatures,
            "statistics": {
                "total_workflows": len(self.workflows),
                "total_data_flows": len(self.data_flows),
                "total_schemas": len(self.schemas),
                "total_artifacts": len(self.artifacts),
            }
        }
        
        logger.info(
            f"Found {len(self.workflows)} workflows, "
            f"{len(self.data_flows)} data flows, "
            f"{len(self.schemas)} schemas"
        )
        
        return result
    
    def _detect_workflows(self, result: ExtractionResult):
        """Detect pipeline/workflow definitions."""
        # Kubeflow patterns
        kfp_patterns = [
            r"@dsl\.pipeline",
            r"@kfp\.dsl\.pipeline",
            r"kfp\.dsl\.ContainerOp",
            r"\.add_step\(",
        ]
        
        # ClearML patterns
        clearml_patterns = [
            r"Task\.init\(",
            r"PipelineController",
            r"\.add_step\(",
        ]
        
        # Slurm job patterns
        slurm_patterns = [
            r"sbatch",
            r"SlurmJob",
            r"submit.*job",
        ]
        
        for entity in result.entities:
            if entity.entity_type not in [CodeEntityType.FUNCTION, CodeEntityType.CLASS]:
                continue
            
            text = f"{entity.documentation or ''} {entity.signature or ''}"
            
            # Detect workflow type
            workflow_type = None
            if any(re.search(p, text, re.IGNORECASE) for p in kfp_patterns):
                workflow_type = "kubeflow"
            elif any(re.search(p, text, re.IGNORECASE) for p in clearml_patterns):
                workflow_type = "clearml"
            elif any(re.search(p, text, re.IGNORECASE) for p in slurm_patterns):
                workflow_type = "slurm"
            
            if workflow_type:
                self.workflows[entity.id] = {
                    "id": entity.id,
                    "name": entity.name,
                    "type": workflow_type,
                    "file": entity.file_path,
                    "entity_type": entity.entity_type.value,
                    "steps": [],
                }
    
    def _extract_io_signatures(
        self, result: ExtractionResult
    ) -> dict[str, dict[str, Any]]:
        """Extract input/output signatures from functions."""
        signatures = {}
        
        for entity in result.entities:
            if entity.entity_type not in [CodeEntityType.FUNCTION, CodeEntityType.METHOD]:
                continue
            
            sig = entity.signature or ""
            doc = entity.documentation or ""
            
            # Parse type hints from signature
            inputs = self._parse_parameters(sig)
            outputs = self._parse_return_type(sig)
            
            # Enhance with docstring info
            doc_info = self._parse_docstring(doc)
            
            signatures[entity.id] = {
                "function": entity.name,
                "inputs": inputs,
                "outputs": outputs,
                "input_description": doc_info.get("params", {}),
                "output_description": doc_info.get("returns"),
                "file": entity.file_path,
            }
        
        return signatures
    
    def _parse_parameters(self, signature: str) -> list[dict[str, Any]]:
        """Parse function parameters with types."""
        params = []
        
        # Extract parameter list
        match = re.search(r"\((.*?)\)", signature)
        if not match:
            return params
        
        param_str = match.group(1)
        
        # Split by comma (simple parsing, doesn't handle nested types)
        for param in param_str.split(","):
            param = param.strip()
            if not param or param == "self" or param == "cls":
                continue
            
            # Parse name and type
            if ":" in param:
                name, type_hint = param.split(":", 1)
                name = name.strip()
                type_hint = type_hint.strip()
                
                # Remove default value
                if "=" in type_hint:
                    type_hint = type_hint.split("=")[0].strip()
                
                params.append({
                    "name": name,
                    "type": type_hint,
                })
            else:
                name = param.split("=")[0].strip()
                params.append({
                    "name": name,
                    "type": "Any",
                })
        
        return params
    
    def _parse_return_type(self, signature: str) -> Optional[str]:
        """Parse return type annotation."""
        match = re.search(r"->\s*([^:]+)", signature)
        if match:
            return match.group(1).strip()
        return None
    
    def _parse_docstring(self, docstring: str) -> dict[str, Any]:
        """Parse docstring for parameter and return descriptions."""
        info = {"params": {}, "returns": None}
        
        if not docstring:
            return info
        
        # Simple parsing for Google/NumPy style docstrings
        lines = docstring.split("\n")
        
        current_section = None
        for line in lines:
            line = line.strip()
            
            # Detect sections
            if line.lower().startswith("args:") or line.lower().startswith("parameters:"):
                current_section = "params"
                continue
            elif line.lower().startswith("returns:"):
                current_section = "returns"
                continue
            
            # Parse parameter descriptions
            if current_section == "params":
                match = re.match(r"(\w+):\s*(.*)", line)
                if match:
                    param_name = match.group(1)
                    description = match.group(2)
                    info["params"][param_name] = description
            
            # Parse return description
            elif current_section == "returns":
                if line and not line.endswith(":"):
                    info["returns"] = line
        
        return info
    
    def _build_data_flows(
        self, result: ExtractionResult, io_signatures: dict[str, dict[str, Any]]
    ):
        """Build data flow graph from function calls."""
        # Map entity IDs to signatures
        for rel in result.relationships:
            if rel.relationship_type != CodeRelationType.CALLS:
                continue
            
            source_sig = io_signatures.get(rel.source_entity_id)
            target_sig = io_signatures.get(rel.target_entity_id)
            
            if source_sig and target_sig:
                # Infer data flow
                self.data_flows.append({
                    "from": source_sig["function"],
                    "from_file": source_sig["file"],
                    "to": target_sig["function"],
                    "to_file": target_sig["file"],
                    "from_outputs": source_sig["outputs"],
                    "to_inputs": target_sig["inputs"],
                })
    
    def _detect_schemas(self, result: ExtractionResult):
        """Detect Pydantic models and data schemas."""
        for entity in result.entities:
            if entity.entity_type != CodeEntityType.CLASS:
                continue
            
            # Check if it's a Pydantic model
            is_pydantic = False
            bases = entity.attributes.get("bases", [])
            
            if isinstance(bases, list):
                is_pydantic = any(
                    "BaseModel" in base or "pydantic" in base.lower()
                    for base in bases
                )
            
            if is_pydantic:
                self.schemas[entity.id] = {
                    "id": entity.id,
                    "name": entity.name,
                    "file": entity.file_path,
                    "type": "pydantic",
                    "fields": [],  # Would need to parse class body
                }
    
    def _detect_artifacts(self, result: ExtractionResult):
        """Detect file operations and artifacts."""
        file_patterns = [
            r"open\(['\"]([^'\"]+)['\"]",
            r"Path\(['\"]([^'\"]+)['\"]",
            r"\.read\(\)",
            r"\.write\(",
            r"\.save\(",
            r"\.load\(",
            r"pickle\.",
            r"json\.",
            r"csv\.",
            r"pd\.read_",
            r"pd\.to_",
        ]
        
        for entity in result.entities:
            if entity.entity_type not in [CodeEntityType.FUNCTION, CodeEntityType.METHOD]:
                continue
            
            # Simple detection from function name and docs
            text = f"{entity.name} {entity.documentation or ''}"
            
            for pattern in file_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    artifact_path = match.group(1) if match.groups() else None
                    
                    self.artifacts.append({
                        "function": entity.name,
                        "file": entity.file_path,
                        "pattern": pattern,
                        "artifact_path": artifact_path,
                    })


class WorkflowSequenceDetector:
    """Detect step sequences in workflows."""
    
    def detect_sequences(
        self, workflows: dict[str, dict[str, Any]], relationships: list[CodeRelationship]
    ) -> dict[str, list[dict[str, Any]]]:
        """Detect step sequences in workflows."""
        sequences = {}
        
        for workflow_id, workflow_info in workflows.items():
            # Find all functions called from this workflow
            steps = []
            
            for rel in relationships:
                if rel.source_entity_id == workflow_id and rel.relationship_type == CodeRelationType.CALLS:
                    steps.append({
                        "step_id": rel.target_entity_id,
                        "order": len(steps) + 1,
                    })
            
            sequences[workflow_id] = steps
        
        return sequences
