"""JavaVisitor: tree-sitter AST visitor for Java source files."""

from __future__ import annotations

from tree_sitter import Node, Tree

from app.services.c4.components.models import CodeElement, CodeElementKind
from app.services.c4.components.parsing.visitors.base_visitor import BaseVisitor

_SPRING_ANNOTATION_MAP: dict[str, str] = {
    "Controller": "controller",
    "RestController": "controller",
    "Service": "service",
    "Repository": "repository",
    "Configuration": "config",
}
_SKIP_ANNOTATIONS: frozenset[str] = frozenset({"Entity"})


class JavaVisitor(BaseVisitor):
    """Extracts CodeElement objects from Java source via tree-sitter."""

    @property
    def supported_languages(self) -> list[str]:
        return ["java"]

    def visit(self, tree: Tree, file_path: str, source: bytes) -> list[CodeElement]:
        package = ""
        imports: list[str] = []
        elements: list[CodeElement] = []

        for node in tree.root_node.children:
            if node.type == "package_declaration":
                package = self._extract_package(node, source)
            elif node.type == "import_declaration":
                imp = self._extract_import(node, source)
                if imp:
                    imports.append(imp)
            elif node.type == "class_declaration":
                el = self._handle_class(node, source, file_path, package)
                if el is not None:
                    elements.extend(el)
            elif node.type == "interface_declaration":
                el = self._handle_interface(node, source, file_path, package)
                if el is not None:
                    elements.append(el)

        for el in elements:
            el.imports = list(imports)

        return elements

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_package(self, node: Node, source: bytes) -> str:
        for child in node.children:
            if child.type in ("scoped_identifier", "identifier"):
                return self._node_text(child, source)
        return ""

    def _extract_import(self, node: Node, source: bytes) -> str:
        for child in node.children:
            if child.type in ("scoped_identifier", "identifier"):
                return self._node_text(child, source)
        return ""

    def _extract_annotations(self, modifiers_node: Node, source: bytes) -> list[str]:
        names: list[str] = []
        for child in modifiers_node.children:
            if child.type in ("marker_annotation", "annotation"):
                for sub in child.children:
                    if sub.type == "identifier":
                        names.append(self._node_text(sub, source))
                        break
        return names

    def _handle_class(
        self, node: Node, source: bytes, file_path: str, package: str
    ) -> list[CodeElement] | None:
        raw_annotations: list[str] = []
        name = ""
        class_body: Node | None = None

        for child in node.children:
            if child.type == "modifiers":
                raw_annotations = self._extract_annotations(child, source)
            elif child.type == "identifier":
                name = self._node_text(child, source)
            elif child.type == "class_body":
                class_body = child

        if any(a in _SKIP_ANNOTATIONS for a in raw_annotations):
            return None

        semantic: list[str] = [
            _SPRING_ANNOTATION_MAP[a] for a in raw_annotations if a in _SPRING_ANNOTATION_MAP
        ]

        layer = self._detect_layer(semantic, name)
        class_el = CodeElement(
            qualified_name=self._qualified_name(file_path, name, package),
            kind=CodeElementKind.CLASS,
            file_path=file_path,
            language="java",
            annotations=raw_annotations,
            layer=layer,
        )

        results: list[CodeElement] = [class_el]

        if class_body is not None:
            for child in class_body.children:
                if child.type == "method_declaration":
                    method_el = self._handle_method(child, source, file_path, package)
                    if method_el is not None:
                        results.append(method_el)

        return results

    def _handle_interface(
        self, node: Node, source: bytes, file_path: str, package: str
    ) -> CodeElement | None:
        raw_annotations: list[str] = []
        name = ""

        for child in node.children:
            if child.type == "modifiers":
                raw_annotations = self._extract_annotations(child, source)
            elif child.type == "identifier":
                name = self._node_text(child, source)

        if any(a in _SKIP_ANNOTATIONS for a in raw_annotations):
            return None

        semantic: list[str] = [
            _SPRING_ANNOTATION_MAP[a] for a in raw_annotations if a in _SPRING_ANNOTATION_MAP
        ]

        layer = self._detect_layer(semantic, name)
        return CodeElement(
            qualified_name=self._qualified_name(file_path, name, package),
            kind=CodeElementKind.INTERFACE,
            file_path=file_path,
            language="java",
            annotations=raw_annotations,
            layer=layer,
        )

    def _handle_method(
        self, node: Node, source: bytes, file_path: str, package: str
    ) -> CodeElement | None:
        is_public = False
        name = ""

        for child in node.children:
            if child.type == "modifiers":
                for mod in child.children:
                    if self._node_text(mod, source) == "public":
                        is_public = True
            elif child.type == "identifier":
                name = self._node_text(child, source)

        if not is_public or not name:
            return None

        return CodeElement(
            qualified_name=self._qualified_name(file_path, name, package),
            kind=CodeElementKind.FUNCTION,
            file_path=file_path,
            language="java",
            annotations=[],
            layer=self._detect_layer([], name),
        )
