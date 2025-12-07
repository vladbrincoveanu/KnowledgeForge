"""JavaScript/TypeScript code extractor."""

import logging
import re
from pathlib import Path
from typing import Optional

from domain.models.code_entities import (
    CodeEntity,
    CodeEntityType,
    CodeLanguage,
    CodeRelationship,
    CodeRelationType,
    SourceType,
)
from services.code_extraction.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class JavaScriptExtractor(BaseExtractor):
    """Extract entities and relationships from JavaScript/TypeScript files."""
    
    # Regex patterns for basic extraction (AST would be better but requires esprima/babel)
    CLASS_PATTERN = re.compile(r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?')
    FUNCTION_PATTERN = re.compile(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)')
    ARROW_FUNCTION_PATTERN = re.compile(r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>')
    IMPORT_PATTERN = re.compile(r'import\s+(?:{([^}]+)}|(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]')
    EXPORT_PATTERN = re.compile(r'export\s+(?:{([^}]+)}|default\s+(\w+))')
    
    def can_handle(self, file_path: Path) -> bool:
        """Check if file is JavaScript or TypeScript."""
        return file_path.suffix in ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']
    
    def extract(self, file_path: Path) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and relationships from JS/TS file."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships
        
        rel_path = self.get_relative_path(file_path)
        language = self._detect_language(file_path)
        
        # Create module entity
        module_name = file_path.stem
        module_id = self.generate_entity_id(rel_path, module_name, "module")
        
        module_entity = CodeEntity(
            id=module_id,
            name=module_name,
            entity_type=CodeEntityType.MODULE,
            language=language,
            source_type=SourceType.CODE,
            file_path=rel_path,
            line_start=1,
            confidence=1.0,
        )
        entities.append(module_entity)
        
        lines = content.split('\n')
        
        # Extract classes
        for line_num, line in enumerate(lines, 1):
            class_match = self.CLASS_PATTERN.search(line)
            if class_match:
                class_name = class_match.group(1)
                base_class = class_match.group(2) if class_match.lastindex >= 2 else None
                
                class_entity, class_rels = self._extract_class(
                    class_name, base_class, line_num, rel_path, language, module_id
                )
                entities.append(class_entity)
                relationships.extend(class_rels)
        
        # Extract functions
        for line_num, line in enumerate(lines, 1):
            func_match = self.FUNCTION_PATTERN.search(line)
            if func_match:
                func_name = func_match.group(1)
                params = func_match.group(2)
                
                func_entity = self._extract_function(
                    func_name, params, line_num, rel_path, language, module_id
                )
                entities.append(func_entity)
            
            # Arrow functions
            arrow_match = self.ARROW_FUNCTION_PATTERN.search(line)
            if arrow_match:
                func_name = arrow_match.group(1)
                
                func_entity = self._extract_function(
                    func_name, "", line_num, rel_path, language, module_id
                )
                entities.append(func_entity)
        
        # Extract imports
        for line_num, line in enumerate(lines, 1):
            import_match = self.IMPORT_PATTERN.search(line)
            if import_match:
                import_rels = self._extract_imports(
                    import_match, line_num, line, rel_path, module_id
                )
                relationships.extend(import_rels)
        
        return entities, relationships
    
    def _detect_language(self, file_path: Path) -> CodeLanguage:
        """Detect if file is JavaScript or TypeScript."""
        if file_path.suffix in ['.ts', '.tsx']:
            return CodeLanguage.TYPESCRIPT
        return CodeLanguage.JAVASCRIPT
    
    def _extract_class(
        self,
        class_name: str,
        base_class: Optional[str],
        line_num: int,
        file_path: str,
        language: CodeLanguage,
        module_id: str
    ) -> tuple[CodeEntity, list[CodeRelationship]]:
        """Extract class entity and inheritance relationships."""
        entity_id = self.generate_entity_id(file_path, class_name, "class")
        relationships: list[CodeRelationship] = []
        
        entity = CodeEntity(
            id=entity_id,
            name=class_name,
            entity_type=CodeEntityType.CLASS,
            language=language,
            source_type=SourceType.CODE,
            file_path=file_path,
            line_start=line_num,
            parent_entity_id=module_id,
            confidence=0.9,
        )
        
        # Add inheritance relationship
        if base_class:
            base_id = self.generate_entity_id(file_path, base_class, "class")
            rel_id = self.generate_relationship_id(entity_id, base_id, "extends")
            
            relationships.append(CodeRelationship(
                id=rel_id,
                source_entity_id=entity_id,
                target_entity_id=base_id,
                relationship_type=CodeRelationType.EXTENDS,
                line_number=line_num,
                confidence=0.9,
            ))
        
        return entity, relationships
    
    def _extract_function(
        self,
        func_name: str,
        params: str,
        line_num: int,
        file_path: str,
        language: CodeLanguage,
        module_id: str
    ) -> CodeEntity:
        """Extract function entity."""
        entity_id = self.generate_entity_id(file_path, func_name, "function")
        
        signature = f"{func_name}({params})" if params else func_name
        
        return CodeEntity(
            id=entity_id,
            name=func_name,
            entity_type=CodeEntityType.FUNCTION,
            language=language,
            source_type=SourceType.CODE,
            file_path=file_path,
            line_start=line_num,
            signature=signature,
            parent_entity_id=module_id,
            confidence=0.9,
        )
    
    def _extract_imports(
        self,
        match: re.Match,
        line_num: int,
        line: str,
        file_path: str,
        module_id: str
    ) -> list[CodeRelationship]:
        """Extract import relationships."""
        relationships: list[CodeRelationship] = []
        
        named_imports = match.group(1)
        default_import = match.group(2)
        from_module = match.group(3)
        
        if named_imports:
            # Named imports: import { a, b } from 'module'
            imports = [name.strip() for name in named_imports.split(',')]
            for imp in imports:
                target_id = self.generate_entity_id(file_path, f"{from_module}.{imp}", "module")
                rel_id = self.generate_relationship_id(module_id, target_id, "imports")
                
                relationships.append(CodeRelationship(
                    id=rel_id,
                    source_entity_id=module_id,
                    target_entity_id=target_id,
                    relationship_type=CodeRelationType.IMPORTS,
                    context=line.strip(),
                    line_number=line_num,
                    attributes={"from_module": from_module, "import_name": imp},
                    confidence=0.9,
                ))
        
        if default_import:
            # Default import: import React from 'react'
            target_id = self.generate_entity_id(file_path, from_module, "module")
            rel_id = self.generate_relationship_id(module_id, target_id, "imports")
            
            relationships.append(CodeRelationship(
                id=rel_id,
                source_entity_id=module_id,
                target_entity_id=target_id,
                relationship_type=CodeRelationType.IMPORTS,
                context=line.strip(),
                line_number=line_num,
                attributes={"from_module": from_module, "default": True},
                confidence=0.9,
            ))
        
        return relationships

