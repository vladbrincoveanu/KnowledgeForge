"""TypeScriptVisitor: tree-sitter AST visitor for TypeScript/JavaScript source files."""

from __future__ import annotations

import os
import re

from tree_sitter import Node, Tree

from app.services.c4.components.models import CodeElement, CodeElementKind
from app.services.c4.components.parsing.visitors.base_visitor import BaseVisitor

_NESTJS_ANNOTATION_MAP: dict[str, str] = {
    "Controller": "controller",
    "Injectable": "injectable",
    "Get": "route",
    "Post": "route",
    "Put": "route",
    "Delete": "route",
    "Patch": "route",
}
_SKIP_ANNOTATIONS: frozenset[str] = frozenset({"Module"})
_DECORATOR_NAME_RE = re.compile(r"@(\w+)")


class TypeScriptVisitor(BaseVisitor):
    """Extracts CodeElement objects from TypeScript/JavaScript source via tree-sitter."""

    @property
    def supported_languages(self) -> list[str]:
        return ["typescript", "tsx", "javascript"]

    def visit(self, tree: Tree, file_path: str, source: bytes) -> list[CodeElement]:
        ext_map = {".ts": "typescript", ".tsx": "tsx", ".js": "javascript", ".jsx": "javascript"}
        language = ext_map.get(os.path.splitext(file_path)[1].lower(), "typescript")

        imports: list[str] = []
        elements: list[CodeElement] = []
        is_express = False

        for node in tree.root_node.children:
            if node.type == "import_statement":
                imp = self._extract_esm_import(node, source)
                if imp:
                    imports.append(imp)
            elif node.type == "lexical_declaration":
                imp, express = self._extract_from_lexical(node, source)
                if imp:
                    imports.append(imp)
                if express:
                    is_express = True
            elif node.type == "export_statement":
                export_decorators = self._get_decorators(node, source)
                inner = self._unwrap_export(node)
                if inner is not None:
                    if inner.type == "class_declaration":
                        el = self._handle_class(
                            inner, source, file_path, language, extra_decorators=export_decorators
                        )
                        if el is not None:
                            elements.append(el)
                    elif inner.type == "function_declaration":
                        el = self._handle_function(inner, source, file_path, language, is_express)
                        if el is not None:
                            elements.append(el)
            elif node.type == "class_declaration":
                el = self._handle_class(node, source, file_path, language)
                if el is not None:
                    elements.append(el)
            elif node.type == "function_declaration":
                el = self._handle_function(node, source, file_path, language, is_express)
                if el is not None:
                    elements.append(el)

        for el in elements:
            el.imports = list(imports)

        return elements

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_esm_import(self, node: Node, source: bytes) -> str:
        source_node = node.child_by_field_name("source")
        if source_node:
            return self._node_text(source_node, source).strip("'\"")
        for child in node.children:
            if child.type == "string":
                return self._node_text(child, source).strip("'\"")
        return ""

    def _extract_from_lexical(self, node: Node, source: bytes) -> tuple[str, bool]:
        """Return (required_module_or_empty, is_express_router)."""
        imp = ""
        is_express = False

        full_text = self._node_text(node, source)
        if "express.Router()" in full_text:
            is_express = True

        for child in node.children:
            if child.type == "variable_declarator":
                value = child.child_by_field_name("value")
                if value and value.type == "call_expression":
                    fn = value.child_by_field_name("function")
                    if fn and self._node_text(fn, source) == "require":
                        args = value.child_by_field_name("arguments")
                        if args:
                            for a in args.children:
                                if a.type == "string":
                                    imp = self._node_text(a, source).strip("'\"")

        return imp, is_express

    def _unwrap_export(self, node: Node) -> Node | None:
        for child in node.children:
            if child.type in ("class_declaration", "function_declaration"):
                return child
        return None

    def _get_decorators(self, node: Node, source: bytes) -> list[str]:
        names: list[str] = []
        for child in node.children:
            if child.type == "decorator":
                text = self._node_text(child, source)
                m = _DECORATOR_NAME_RE.match(text)
                if m:
                    names.append(m.group(1))
        return names

    def _handle_class(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        language: str,
        extra_decorators: list[str] | None = None,
    ) -> CodeElement | None:
        decorator_names = (extra_decorators or []) + self._get_decorators(node, source)
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        name = self._node_text(name_node, source)

        if any(a in _SKIP_ANNOTATIONS for a in decorator_names):
            return None

        semantic: list[str] = []
        for ann in decorator_names:
            mapped = _NESTJS_ANNOTATION_MAP.get(ann)
            if mapped == "injectable":
                if name.endswith("Service"):
                    semantic.append("service")
                elif name.endswith("Repository"):
                    semantic.append("repository")
                else:
                    semantic.append("injectable")
            elif mapped:
                semantic.append(mapped)

        layer = self._detect_layer(semantic, name)
        return CodeElement(
            qualified_name=self._qualified_name(file_path, name),
            kind=CodeElementKind.CLASS,
            file_path=file_path,
            language=language,
            annotations=decorator_names,
            layer=layer,
        )

    def _handle_function(
        self, node: Node, source: bytes, file_path: str, language: str, is_express: bool
    ) -> CodeElement | None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        name = self._node_text(name_node, source)
        if not name:
            return None

        semantic: list[str] = ["handler"] if is_express else []
        layer = self._detect_layer(semantic, name)
        return CodeElement(
            qualified_name=self._qualified_name(file_path, name),
            kind=CodeElementKind.FUNCTION,
            file_path=file_path,
            language=language,
            annotations=[],
            layer=layer,
        )
