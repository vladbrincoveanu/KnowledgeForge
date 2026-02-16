"""
Python-specific code extractor using Abstract Syntax Trees (AST).

This extractor provides a deep, detailed analysis of Python source code.
It inherits from BaseExtractor and uses Python's `ast` module to identify:
- Classes and their inheritance
- Functions and their parameters
- Function calls
- Import statements
- Global and local variables

This detailed information is used to build a granular code graph, complementing
the high-level architectural view from the C4 extractor.
"""

import ast
import logging
from pathlib import Path
from typing import Any

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


class PythonASTExtractor(BaseExtractor):
    """
    Extracts detailed code information from Python files using AST.
    """

    def can_handle(self, file_path: Path) -> bool:
        """This extractor handles Python files."""
        return file_path.suffix == ".py"

    def extract(self, file_path: Path) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """
        Extracts entities and relationships from a single Python file.
        """
        logger.debug(f"Starting AST extraction for: {file_path}")
        content = self.safe_read_file(file_path)
        if content is None:
            self.errors.append(f"Could not read file: {file_path}")
            return [], []

        try:
            tree = ast.parse(content, filename=str(file_path))
            visitor = _ASTVisitor(str(self.get_relative_path(file_path)), self)
            visitor.visit(tree)
            
            self.entities.extend(visitor.entities)
            self.relationships.extend(visitor.relationships)
            
            logger.debug(f"Found {len(visitor.entities)} entities and {len(visitor.relationships)} relationships in {file_path}")

        except SyntaxError as e:
            self.errors.append(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            self.errors.append(f"Unexpected error extracting {file_path}: {e}")
            logger.error(f"Failed AST extraction for {file_path}", exc_info=True)

        return self.entities, self.relationships


class _ASTVisitor(ast.NodeVisitor):
    """
    An AST node visitor that extracts entities and relationships.
    """

    def __init__(self, file_path: str, extractor: PythonASTExtractor):
        self.file_path = file_path
        self.extractor = extractor
        self.entities: list[CodeEntity] = []
        self.relationships: list[CodeRelationship] = []
        self.current_scope: list[str] = []
        
        # Create the module entity for the file itself
        module_name = file_path.replace('/', '.').removesuffix('.py')
        module_id = self.extractor.generate_entity_id(self.file_path, module_name, "Module")
        module_entity = CodeEntity(
            id=module_id,
            name=module_name,
            entity_type=CodeEntityType.MODULE,
            language=CodeLanguage.PYTHON,
            source_type=SourceType.CODE,
            file_path=self.file_path,
            signature=None,
            documentation=None,
            parent_entity_id=None,
        )
        self.entities.append(module_entity)
        self.current_scope.append(module_id)

    def _get_full_name(self, name: str) -> str:
        """Gets the fully qualified name within the current scope."""
        # This is a simplification. Real qualification is more complex.
        scope_base = ".".join(e.split("::")[-1] for e in self.current_scope if "::" in e)
        return f"{scope_base}.{name}" if scope_base else name

    def visit_ClassDef(self, node: ast.ClassDef):
        """Extracts ClassEntity and InheritanceRelationships."""
        class_id = self.extractor.generate_entity_id(self.file_path, node.name, "Class")
        
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_name = base.id
                base_classes.append(base_name)
                # We don't know the target_id yet, so we create a placeholder relationship
                rel_id = self.extractor.generate_relationship_id(class_id, base_name, "INHERITS_FROM")
                rel = CodeRelationship(
                    id=rel_id,
                    source_entity_id=class_id,
                    target_entity_id=base_name,
                    relationship_type=CodeRelationType.INHERITS_FROM,
                    context=f"class {node.name} inherits from {base_name}",
                    attributes={"target_entity_name": base_name},
                )
                self.relationships.append(rel)

        class_entity = CodeEntity(
            id=class_id,
            name=node.name,
            entity_type=CodeEntityType.CLASS,
            language=CodeLanguage.PYTHON,
            source_type=SourceType.CODE,
            file_path=self.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno,
            signature=None,
            documentation=ast.get_docstring(node),
            parent_entity_id=None,
            attributes={'base_classes': base_classes},
        )
        self.entities.append(class_entity)

        # Enter class scope
        self.current_scope.append(class_id)
        self.generic_visit(node)
        # Exit class scope
        self.current_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Extracts FunctionEntity with decorators."""
        func_id = self.extractor.generate_entity_id(self.file_path, node.name, "Function")
        
        params = [arg.arg for arg in node.args.args]
        signature = f"{node.name}({', '.join(params)})"
        
        # Extract decorators
        decorators = []
        for decorator in node.decorator_list:
            dec_name = self._get_decorator_name(decorator)
            if dec_name:
                decorators.append(dec_name)
        
        func_entity = CodeEntity(
            id=func_id,
            name=node.name,
            entity_type=CodeEntityType.FUNCTION,
            language=CodeLanguage.PYTHON,
            source_type=SourceType.CODE,
            file_path=self.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno,
            signature=signature,
            documentation=ast.get_docstring(node),
            parent_entity_id=self.current_scope[-1],
            attributes={
                'parameters': params,
                'decorators': decorators,
            },
        )
        self.entities.append(func_entity)

        # Enter function scope
        self.current_scope.append(func_id)
        self.generic_visit(node)
        # Exit function scope
        self.current_scope.pop()

    def visit_Import(self, node: ast.Import):
        """Extracts ImportRelationships for `import x`."""
        for alias in node.names:
            rel_id = self.extractor.generate_relationship_id(self.current_scope[0], alias.name, "IMPORTS")
            rel = CodeRelationship(
                id=rel_id,
                source_entity_id=self.current_scope[0], # Module ID
                target_entity_id=alias.name,
                relationship_type=CodeRelationType.IMPORTS,
                context=f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""),
                attributes={"target_entity_name": alias.name},
            )
            self.relationships.append(rel)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Extracts ImportRelationships for `from x import y`."""
        module_name = node.module or ""
        for alias in node.names:
            target_name = f"{module_name}.{alias.name}" if module_name else alias.name
            rel_id = self.extractor.generate_relationship_id(self.current_scope[0], target_name, "IMPORTS")
            rel = CodeRelationship(
                id=rel_id,
                source_entity_id=self.current_scope[0], # Module ID
                target_entity_id=target_name,
                relationship_type=CodeRelationType.IMPORTS,
                context=f"from {module_name} import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""),
                attributes={"target_entity_name": target_name},
            )
            self.relationships.append(rel)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Extracts CallRelationships."""
        
        # This is a simplified way to get the function name.
        # It doesn't handle complex cases like `a.b.c()`.
        target_name = ""
        if isinstance(node.func, ast.Name):
            target_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # Trying to reconstruct the call chain, e.g., "os.path.join"
            # This is still a simplification.
            parts = []
            curr = node.func
            while isinstance(curr, ast.Attribute):
                parts.insert(0, curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.insert(0, curr.id)
            target_name = ".".join(parts)

        if target_name:
            rel_id = self.extractor.generate_relationship_id(self.current_scope[-1], target_name, "CALLS")
            rel = CodeRelationship(
                id=rel_id,
                source_entity_id=self.current_scope[-1], # ID of the calling function/class/module
                target_entity_id=target_name, # Placeholder
                relationship_type=CodeRelationType.CALLS,
                context=f"call to {target_name}",
                attributes={"target_entity_name": target_name},
            )
            self.relationships.append(rel)
            
        self.generic_visit(node)
    
    def _get_decorator_name(self, decorator) -> str:
        """Extract decorator name from AST node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            # Handle @app.get, @router.post, etc.
            parts = []
            curr = decorator
            while isinstance(curr, ast.Attribute):
                parts.insert(0, curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.insert(0, curr.id)
            return ".".join(parts)
        elif isinstance(decorator, ast.Call):
            # Handle @decorator() or @app.get("/path")
            return self._get_decorator_name(decorator.func)
        return ""
