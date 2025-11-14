"""Infrastructure-as-Code (IaC) extractor for Terraform and Pulumi."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from app.domain.models.code_entities import (
    CodeEntity,
    CodeEntityType,
    CodeLanguage,
    CodeRelationship,
    CodeRelationType,
    SourceType,
)
from app.services.code_extraction.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class IaCExtractor(BaseExtractor):
    """Extract entities and relationships from IaC files (Terraform, Pulumi)."""
    
    def can_handle(self, file_path: Path) -> bool:
        """Check if file is an IaC configuration file."""
        # Terraform
        if file_path.suffix == '.tf':
            return True
        
        # Pulumi (Python, TypeScript, Go, C#)
        if file_path.name in ['Pulumi.yaml', 'Pulumi.dev.yaml', 'Pulumi.prod.yaml']:
            return True
        
        # Terraform JSON
        if file_path.suffix == '.tf.json':
            return True
        
        return False
    
    def extract(self, file_path: Path) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and relationships from IaC file."""
        if file_path.suffix == '.tf':
            return self._extract_terraform_hcl(file_path)
        elif file_path.suffix == '.tf.json':
            return self._extract_terraform_json(file_path)
        elif 'pulumi' in file_path.name.lower():
            return self._extract_pulumi(file_path)
        
        return [], []
    
    def _extract_terraform_hcl(
        self,
        file_path: Path
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract from Terraform HCL file (basic regex-based extraction)."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships
        
        rel_path = self.get_relative_path(file_path)
        
        # Resource pattern: resource "type" "name" { ... }
        resource_pattern = re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{')
        
        # Data source pattern: data "type" "name" { ... }
        data_pattern = re.compile(r'data\s+"([^"]+)"\s+"([^"]+)"\s*\{')
        
        # Module pattern: module "name" { ... }
        module_pattern = re.compile(r'module\s+"([^"]+)"\s*\{')
        
        # Variable pattern: variable "name" { ... }
        variable_pattern = re.compile(r'variable\s+"([^"]+)"\s*\{')
        
        # Output pattern: output "name" { ... }
        output_pattern = re.compile(r'output\s+"([^"]+)"\s*\{')
        
        # Extract resources
        for match in resource_pattern.finditer(content):
            resource_type = match.group(1)
            resource_name = match.group(2)
            line_num = content[:match.start()].count('\n') + 1
            
            entity_id = self.generate_entity_id(rel_path, f"{resource_type}.{resource_name}", "resource")
            
            entity = CodeEntity(
                id=entity_id,
                name=resource_name,
                entity_type=CodeEntityType.RESOURCE,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.IAC,
                file_path=rel_path,
                line_start=line_num,
                attributes={
                    "resource_type": resource_type,
                    "iac_tool": "terraform",
                },
                confidence=0.9,
            )
            entities.append(entity)
        
        # Extract data sources
        for match in data_pattern.finditer(content):
            data_type = match.group(1)
            data_name = match.group(2)
            line_num = content[:match.start()].count('\n') + 1
            
            entity_id = self.generate_entity_id(rel_path, f"data.{data_type}.{data_name}", "data_source")
            
            entity = CodeEntity(
                id=entity_id,
                name=data_name,
                entity_type=CodeEntityType.DATA_SOURCE,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.IAC,
                file_path=rel_path,
                line_start=line_num,
                attributes={
                    "data_type": data_type,
                    "iac_tool": "terraform",
                },
                confidence=0.9,
            )
            entities.append(entity)
        
        # Extract modules
        for match in module_pattern.finditer(content):
            module_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            entity_id = self.generate_entity_id(rel_path, f"module.{module_name}", "module_ref")
            
            entity = CodeEntity(
                id=entity_id,
                name=module_name,
                entity_type=CodeEntityType.MODULE_REF,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.IAC,
                file_path=rel_path,
                line_start=line_num,
                attributes={
                    "iac_tool": "terraform",
                },
                confidence=0.9,
            )
            entities.append(entity)
        
        # Extract variables
        for match in variable_pattern.finditer(content):
            var_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            entity_id = self.generate_entity_id(rel_path, f"var.{var_name}", "variable")
            
            entity = CodeEntity(
                id=entity_id,
                name=var_name,
                entity_type=CodeEntityType.VARIABLE,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.IAC,
                file_path=rel_path,
                line_start=line_num,
                attributes={
                    "iac_tool": "terraform",
                    "variable_type": "input",
                },
                confidence=0.9,
            )
            entities.append(entity)
        
        # Extract outputs
        for match in output_pattern.finditer(content):
            output_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            entity_id = self.generate_entity_id(rel_path, f"output.{output_name}", "variable")
            
            entity = CodeEntity(
                id=entity_id,
                name=output_name,
                entity_type=CodeEntityType.VARIABLE,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.IAC,
                file_path=rel_path,
                line_start=line_num,
                attributes={
                    "iac_tool": "terraform",
                    "variable_type": "output",
                },
                confidence=0.9,
            )
            entities.append(entity)
        
        # Extract references between resources (simplified)
        # Pattern: ${resource_type.resource_name.attribute}
        ref_pattern = re.compile(r'\$\{([a-z_]+)\.([a-z0-9_]+)\.([a-z0-9_]+)\}')
        
        for match in ref_pattern.finditer(content):
            target_type = match.group(1)
            target_name = match.group(2)
            attribute = match.group(3)
            line_num = content[:match.start()].count('\n') + 1
            
            # Find which resource this reference is in
            # This is simplified - in production you'd track block contexts
            for entity in entities:
                if entity.file_path == rel_path and entity.line_start:
                    # Create reference relationship
                    target_id = self.generate_entity_id(rel_path, f"{target_type}.{target_name}", "resource")
                    rel_id = self.generate_relationship_id(entity.id, target_id, "references")
                    
                    relationships.append(CodeRelationship(
                        id=rel_id,
                        source_entity_id=entity.id,
                        target_entity_id=target_id,
                        relationship_type=CodeRelationType.REFERENCES,
                        line_number=line_num,
                        attributes={
                            "referenced_attribute": attribute,
                        },
                        confidence=0.8,
                    ))
        
        return entities, relationships
    
    def _extract_terraform_json(
        self,
        file_path: Path
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract from Terraform JSON format."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            rel_path = self.get_relative_path(file_path)
            
            # Extract resources
            for resource_type, resources in data.get('resource', {}).items():
                for resource_name, resource_config in resources.items():
                    entity_id = self.generate_entity_id(
                        rel_path,
                        f"{resource_type}.{resource_name}",
                        "resource"
                    )
                    
                    entity = CodeEntity(
                        id=entity_id,
                        name=resource_name,
                        entity_type=CodeEntityType.RESOURCE,
                        language=CodeLanguage.UNKNOWN,
                        source_type=SourceType.IAC,
                        file_path=rel_path,
                        attributes={
                            "resource_type": resource_type,
                            "iac_tool": "terraform",
                            "config": resource_config,
                        },
                        confidence=1.0,
                    )
                    entities.append(entity)
        
        except Exception as e:
            self.errors.append(f"Failed to parse Terraform JSON {file_path}: {e}")
        
        return entities, relationships
    
    def _extract_pulumi(
        self,
        file_path: Path
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract from Pulumi configuration."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships
        
        rel_path = self.get_relative_path(file_path)
        
        # Pulumi.yaml contains project metadata
        import yaml
        
        try:
            config = yaml.safe_load(content)
            
            if not config:
                return entities, relationships
            
            # Create project entity
            project_name = config.get('name', file_path.stem)
            entity_id = self.generate_entity_id(rel_path, project_name, "project")
            
            entity = CodeEntity(
                id=entity_id,
                name=project_name,
                entity_type=CodeEntityType.MODULE,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.IAC,
                file_path=rel_path,
                attributes={
                    "iac_tool": "pulumi",
                    "runtime": config.get('runtime'),
                    "description": config.get('description'),
                },
                confidence=1.0,
            )
            entities.append(entity)
        
        except Exception as e:
            self.errors.append(f"Failed to parse Pulumi config {file_path}: {e}")
        
        return entities, relationships

