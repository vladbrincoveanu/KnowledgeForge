"""CSharpVisitor: tree-sitter AST visitor for C# source files."""

from __future__ import annotations

from tree_sitter import Node, Tree

from app.services.c4.components.models import ArchitecturalLayer, CodeElement, CodeElementKind
from app.services.c4.components.parsing.visitors.base_visitor import BaseVisitor

_ASPNET_ANNOTATION_MAP: dict[str, str] = {
    "ApiController": "controller",
    "Controller": "controller",
    "HttpGet": "route",
    "HttpPost": "route",
    "HttpPut": "route",
    "HttpDelete": "route",
    "HttpPatch": "route",
    "Authorize": "middleware",
}

_DBCONTEXT_BASE = "DbContext"


class CSharpVisitor(BaseVisitor):
    """Extracts CodeElement objects from C# source via tree-sitter."""

    @property
    def supported_languages(self) -> list[str]:
        return ["csharp"]

    def visit(self, tree: Tree, file_path: str, source: bytes) -> list[CodeElement]:
        usings: list[str] = []
        elements: list[CodeElement] = []

        # Detect file-scoped namespace (sets default namespace for root-level declarations)
        file_namespace = ""
        for node in tree.root_node.children:
            if node.type == "file_scoped_namespace_declaration":
                file_namespace = self._extract_namespace(node, source)
            elif node.type == "using_directive":
                u = self._extract_using(node, source)
                if u:
                    usings.append(u)

        # Collect declarations
        for node in tree.root_node.children:
            if node.type == "namespace_declaration":
                ns = self._extract_namespace(node, source)
                body = node.child_by_field_name("body")
                if body is not None:
                    for child in body.children:
                        self._process_declaration(child, source, file_path, ns, elements)
            else:
                self._process_declaration(node, source, file_path, file_namespace, elements)

        for el in elements:
            el.imports = list(usings)

        return elements

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_namespace(self, node: Node, source: bytes) -> str:
        for child in node.children:
            if child.type in ("qualified_name", "identifier"):
                return self._node_text(child, source)
        return ""

    def _extract_using(self, node: Node, source: bytes) -> str:
        for child in node.children:
            if child.type in ("qualified_name", "identifier"):
                return self._node_text(child, source)
        return ""

    def _extract_attributes(self, node: Node, source: bytes) -> list[str]:
        """Return attribute names from a single attribute_list node."""
        names: list[str] = []
        for child in node.children:
            if child.type == "attribute":
                name_node = child.child_by_field_name("name")
                if name_node is not None:
                    names.append(self._node_text(name_node, source))
                else:
                    for sub in child.children:
                        if sub.type in ("identifier", "qualified_name"):
                            names.append(self._node_text(sub, source))
                            break
        return names

    def _collect_all_attributes(self, node: Node, source: bytes) -> list[str]:
        """Collect attributes from every attribute_list child of *node*."""
        attrs: list[str] = []
        for child in node.children:
            if child.type == "attribute_list":
                attrs.extend(self._extract_attributes(child, source))
        return attrs

    def _extract_base_types(self, base_list_node: Node, source: bytes) -> list[str]:
        types: list[str] = []
        for child in base_list_node.children:
            if child.type in ("identifier", "qualified_name", "generic_name"):
                types.append(self._node_text(child, source))
        return types

    def _process_declaration(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        namespace: str,
        results: list[CodeElement],
    ) -> None:
        if node.type == "class_declaration":
            results.extend(self._handle_class(node, source, file_path, namespace))
        elif node.type == "record_declaration":
            results.append(self._handle_record(node, source, file_path, namespace))
        elif node.type == "interface_declaration":
            results.append(self._handle_interface(node, source, file_path, namespace))

    def _handle_class(
        self, node: Node, source: bytes, file_path: str, namespace: str
    ) -> list[CodeElement]:
        name = ""
        raw_annotations: list[str] = self._collect_all_attributes(node, source)
        base_classes: list[str] = []
        body: Node | None = None

        for child in node.children:
            if child.type == "identifier":
                name = self._node_text(child, source)
            elif child.type == "base_list":
                base_classes = self._extract_base_types(child, source)
            elif child.type == "declaration_list":
                body = child

        if not name:
            return []

        semantic: list[str] = [
            _ASPNET_ANNOTATION_MAP[a] for a in raw_annotations if a in _ASPNET_ANNOTATION_MAP
        ]
        if any(_DBCONTEXT_BASE in bc for bc in base_classes):
            semantic.append("repository")

        layer = self._detect_layer(semantic, name)
        class_el = CodeElement(
            qualified_name=self._qualified_name(file_path, name, namespace),
            kind=CodeElementKind.CLASS,
            file_path=file_path,
            language="csharp",
            annotations=raw_annotations,
            base_classes=base_classes,
            layer=layer,
        )

        elements: list[CodeElement] = [class_el]

        if body is not None:
            for child in body.children:
                if child.type == "method_declaration":
                    method_el = self._handle_method(child, source, file_path, namespace)
                    if method_el is not None:
                        elements.append(method_el)

        return elements

    def _handle_record(
        self, node: Node, source: bytes, file_path: str, namespace: str
    ) -> CodeElement:
        name = ""
        raw_annotations: list[str] = self._collect_all_attributes(node, source)

        for child in node.children:
            if child.type == "identifier":
                name = self._node_text(child, source)

        return CodeElement(
            qualified_name=self._qualified_name(file_path, name, namespace),
            kind=CodeElementKind.CLASS,
            file_path=file_path,
            language="csharp",
            annotations=raw_annotations,
            layer=ArchitecturalLayer.UNKNOWN,
            filtered=True,
            filter_reason="record",
        )

    def _handle_interface(
        self, node: Node, source: bytes, file_path: str, namespace: str
    ) -> CodeElement:
        name = ""
        raw_annotations: list[str] = self._collect_all_attributes(node, source)

        for child in node.children:
            if child.type == "identifier":
                name = self._node_text(child, source)

        semantic: list[str] = [
            _ASPNET_ANNOTATION_MAP[a] for a in raw_annotations if a in _ASPNET_ANNOTATION_MAP
        ]
        layer = self._detect_layer(semantic, name)

        return CodeElement(
            qualified_name=self._qualified_name(file_path, name, namespace),
            kind=CodeElementKind.INTERFACE,
            file_path=file_path,
            language="csharp",
            annotations=raw_annotations,
            layer=layer,
        )

    def _handle_method(
        self, node: Node, source: bytes, file_path: str, namespace: str
    ) -> CodeElement | None:
        is_public = False
        name = ""
        raw_annotations: list[str] = self._collect_all_attributes(node, source)

        for child in node.children:
            if child.type == "modifier" and self._node_text(child, source) == "public":
                is_public = True
            elif child.type == "identifier":
                name = self._node_text(child, source)

        if not is_public or not name:
            return None

        semantic: list[str] = [
            _ASPNET_ANNOTATION_MAP[a] for a in raw_annotations if a in _ASPNET_ANNOTATION_MAP
        ]
        layer = self._detect_layer(semantic, name)

        return CodeElement(
            qualified_name=self._qualified_name(file_path, name, namespace),
            kind=CodeElementKind.FUNCTION,
            file_path=file_path,
            language="csharp",
            annotations=raw_annotations,
            layer=layer,
        )
