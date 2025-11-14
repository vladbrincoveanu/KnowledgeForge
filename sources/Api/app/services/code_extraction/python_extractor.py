"""Python code extractor."""

import ast
import logging
from pathlib import Path
from typing import Optional

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


class PythonExtractor(BaseExtractor):
    """Extract entities and relationships from Python source files."""
    
    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a Python file."""
        return file_path.suffix == '.py'
    
    def extract(self, file_path: Path) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and relationships from Python file."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships
        
        try:
            tree = ast.parse(content, filename=str(file_path))
            rel_path = self.get_relative_path(file_path)
            
            # Extract module-level entities
            module_entity = self._create_module_entity(file_path, rel_path, tree)
            entities.append(module_entity)
            
            # Walk the AST
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_entity, class_rels = self._extract_class(node, rel_path, module_entity.id)
                    entities.append(class_entity)
                    relationships.extend(class_rels)
                    
                    # Extract methods within class
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                            method_entity, method_rels = self._extract_method(
                                item, rel_path, class_entity.id
                            )
                            entities.append(method_entity)
                            relationships.extend(method_rels)
                
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Only top-level functions (not methods)
                    if not any(isinstance(p, ast.ClassDef) for p in ast.walk(tree) if node in getattr(p, 'body', [])):
                        func_entity, func_rels = self._extract_function(
                            node, rel_path, module_entity.id
                        )
                        entities.append(func_entity)
                        relationships.extend(func_rels)
                
                elif isinstance(node, ast.Import):
                    import_rels = self._extract_imports(node, rel_path, module_entity.id)
                    relationships.extend(import_rels)
                
                elif isinstance(node, ast.ImportFrom):
                    import_rels = self._extract_import_from(node, rel_path, module_entity.id)
                    relationships.extend(import_rels)
        
        except SyntaxError as e:
            self.errors.append(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            self.errors.append(f"Failed to parse {file_path}: {e}")
        
        return entities, relationships
    
    def _create_module_entity(
        self,
        file_path: Path,
        rel_path: str,
        tree: ast.Module
    ) -> CodeEntity:
        """Create entity for the module itself."""
        module_name = file_path.stem
        entity_id = self.generate_entity_id(rel_path, module_name, "module")
        
        # Extract module docstring
        docstring = ast.get_docstring(tree)
        
        return CodeEntity(
            id=entity_id,
            name=module_name,
            entity_type=CodeEntityType.MODULE,
            language=CodeLanguage.PYTHON,
            source_type=SourceType.CODE,
            file_path=rel_path,
            line_start=1,
            documentation=docstring,
            confidence=1.0,
        )
    
    def _extract_class(
        self,
        node: ast.ClassDef,
        file_path: str,
        parent_id: Optional[str]
    ) -> tuple[CodeEntity, list[CodeRelationship]]:
        """Extract class entity and its relationships."""
        entity_id = self.generate_entity_id(file_path, node.name, "class")
        relationships: list[CodeRelationship] = []
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        # Extract decorators
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        
        entity = CodeEntity(
            id=entity_id,
            name=node.name,
            entity_type=CodeEntityType.CLASS,
            language=CodeLanguage.PYTHON,
            source_type=SourceType.CODE,
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno,
            documentation=docstring,
            parent_entity_id=parent_id,
            attributes={
                "decorators": decorators,
                "num_methods": sum(1 for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))),
            },
            confidence=1.0,
        )
        
        # Extract inheritance relationships
        for base in node.bases:
            base_name = self._get_name(base)
            if base_name:
                # Create a relationship to the base class
                base_id = self.generate_entity_id(file_path, base_name, "class")
                rel_id = self.generate_relationship_id(entity_id, base_id, "inherits_from")
                
                relationships.append(CodeRelationship(
                    id=rel_id,
                    source_entity_id=entity_id,
                    target_entity_id=base_id,
                    relationship_type=CodeRelationType.INHERITS_FROM,
                    context=f"class {node.name}({base_name})",
                    line_number=node.lineno,
                    confidence=1.0,
                ))
        
        return entity, relationships
    
    def _extract_method(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        class_id: str
    ) -> tuple[CodeEntity, list[CodeRelationship]]:
        """Extract method entity and its relationships."""
        entity_id = self.generate_entity_id(file_path, f"{class_id}.{node.name}", "method")
        relationships: list[CodeRelationship] = []
        
        # Extract signature
        args = [arg.arg for arg in node.args.args]
        signature = f"{node.name}({', '.join(args)})"
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        # Determine modifiers
        modifiers = []
        if node.name.startswith('__') and not node.name.endswith('__'):
            modifiers.append('private')
        elif node.name.startswith('_'):
            modifiers.append('protected')
        
        if isinstance(node, ast.AsyncFunctionDef):
            modifiers.append('async')
        
        # Check for static/class methods
        for decorator in node.decorator_list:
            dec_name = self._get_decorator_name(decorator)
            if dec_name in ['staticmethod', 'classmethod', 'property']:
                modifiers.append(dec_name)
        
        entity = CodeEntity(
            id=entity_id,
            name=node.name,
            entity_type=CodeEntityType.METHOD,
            language=CodeLanguage.PYTHON,
            source_type=SourceType.CODE,
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno,
            signature=signature,
            documentation=docstring,
            modifiers=modifiers,
            parent_entity_id=class_id,
            attributes={
                "num_args": len(args),
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            },
            confidence=1.0,
        )
        
        # Extract function calls within the method
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Call):
                call_name = self._get_name(subnode.func)
                if call_name:
                    # Create CALLS relationship
                    target_id = self.generate_entity_id(file_path, call_name, "function")
                    rel_id = self.generate_relationship_id(entity_id, target_id, "calls")
                    
                    relationships.append(CodeRelationship(
                        id=rel_id,
                        source_entity_id=entity_id,
                        target_entity_id=target_id,
                        relationship_type=CodeRelationType.CALLS,
                        line_number=getattr(subnode, 'lineno', None),
                        confidence=0.8,
                    ))
        
        return entity, relationships
    
    def _extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        parent_id: str
    ) -> tuple[CodeEntity, list[CodeRelationship]]:
        """Extract function entity and its relationships."""
        entity_id = self.generate_entity_id(file_path, node.name, "function")
        relationships: list[CodeRelationship] = []
        
        # Extract signature
        args = [arg.arg for arg in node.args.args]
        signature = f"{node.name}({', '.join(args)})"
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        # Modifiers
        modifiers = []
        if isinstance(node, ast.AsyncFunctionDef):
            modifiers.append('async')
        
        entity = CodeEntity(
            id=entity_id,
            name=node.name,
            entity_type=CodeEntityType.FUNCTION,
            language=CodeLanguage.PYTHON,
            source_type=SourceType.CODE,
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno,
            signature=signature,
            documentation=docstring,
            modifiers=modifiers,
            parent_entity_id=parent_id,
            attributes={
                "num_args": len(args),
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            },
            confidence=1.0,
        )
        
        # Extract function calls
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Call):
                call_name = self._get_name(subnode.func)
                if call_name:
                    target_id = self.generate_entity_id(file_path, call_name, "function")
                    rel_id = self.generate_relationship_id(entity_id, target_id, "calls")
                    
                    relationships.append(CodeRelationship(
                        id=rel_id,
                        source_entity_id=entity_id,
                        target_entity_id=target_id,
                        relationship_type=CodeRelationType.CALLS,
                        line_number=getattr(subnode, 'lineno', None),
                        confidence=0.8,
                    ))
        
        return entity, relationships
    
    def _extract_imports(
        self,
        node: ast.Import,
        file_path: str,
        module_id: str
    ) -> list[CodeRelationship]:
        """Extract import relationships."""
        relationships: list[CodeRelationship] = []
        
        for alias in node.names:
            target_name = alias.asname if alias.asname else alias.name
            target_id = self.generate_entity_id(file_path, target_name, "module")
            rel_id = self.generate_relationship_id(module_id, target_id, "imports")
            
            relationships.append(CodeRelationship(
                id=rel_id,
                source_entity_id=module_id,
                target_entity_id=target_id,
                relationship_type=CodeRelationType.IMPORTS,
                context=f"import {alias.name}",
                line_number=node.lineno,
                attributes={"imported_name": alias.name, "alias": alias.asname},
                confidence=1.0,
            ))
        
        return relationships
    
    def _extract_import_from(
        self,
        node: ast.ImportFrom,
        file_path: str,
        module_id: str
    ) -> list[CodeRelationship]:
        """Extract 'from ... import ...' relationships."""
        relationships: list[CodeRelationship] = []
        
        module_name = node.module or ""
        
        for alias in node.names:
            target_name = f"{module_name}.{alias.name}" if module_name else alias.name
            target_id = self.generate_entity_id(file_path, target_name, "module")
            rel_id = self.generate_relationship_id(module_id, target_id, "imports")
            
            relationships.append(CodeRelationship(
                id=rel_id,
                source_entity_id=module_id,
                target_entity_id=target_id,
                relationship_type=CodeRelationType.IMPORTS,
                context=f"from {module_name} import {alias.name}",
                line_number=node.lineno,
                attributes={
                    "from_module": module_name,
                    "imported_name": alias.name,
                    "alias": alias.asname,
                },
                confidence=1.0,
            ))
        
        return relationships
    
    def _get_name(self, node: ast.AST) -> Optional[str]:
        """Extract name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_name(node.value)
            return f"{value}.{node.attr}" if value else node.attr
        elif isinstance(node, ast.Call):
            return self._get_name(node.func)
        return None
    
    def _get_decorator_name(self, node: ast.AST) -> Optional[str]:
        """Extract decorator name."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return None

