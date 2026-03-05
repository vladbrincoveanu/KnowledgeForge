"""GoVisitor: tree-sitter AST visitor for Go source files."""

from __future__ import annotations

import re

from tree_sitter import Node, Tree

from app.services.c4.components.models import ArchitecturalLayer, CodeElement, CodeElementKind
from app.services.c4.components.parsing.visitors.base_visitor import BaseVisitor

_CONTROLLER_FUNC_RE = re.compile(r"^(Handle|Get|Post)")


class GoVisitor(BaseVisitor):
    """Extracts CodeElement objects from Go source via tree-sitter."""

    @property
    def supported_languages(self) -> list[str]:
        return ["go"]

    def visit(self, tree: Tree, file_path: str, source: bytes) -> list[CodeElement]:
        package = ""
        imports: list[str] = []
        elements: list[CodeElement] = []
        # Maps bare struct name → its CodeElement so we can update layer later.
        struct_map: dict[str, CodeElement] = {}
        # Struct names that have at least one HTTP handler method.
        handler_receiver_types: set[str] = set()

        for node in tree.root_node.children:
            if node.type == "package_clause":
                package = self._extract_package(node, source)
            elif node.type == "import_declaration":
                imports.extend(self._extract_imports(node, source))
            elif node.type == "type_declaration":
                new_els, structs = self._handle_type_decl(node, source, file_path, package)
                elements.extend(new_els)
                struct_map.update(structs)
            elif node.type == "function_declaration":
                el = self._handle_function(node, source, file_path, package)
                if el is not None:
                    elements.append(el)
            elif node.type == "method_declaration":
                if self._is_http_handler(node, source):
                    recv = self._get_receiver_type_name(node, source)
                    if recv:
                        handler_receiver_types.add(recv)

        # Promote handler structs to PRESENTATION layer.
        for recv_name in handler_receiver_types:
            if recv_name in struct_map:
                struct_map[recv_name].layer = self._detect_layer(["handler"], recv_name)

        for el in elements:
            el.imports = list(imports)

        return elements

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_package(self, node: Node, source: bytes) -> str:
        for child in node.children:
            if child.type == "package_identifier":
                return self._node_text(child, source)
        return ""

    def _extract_imports(self, node: Node, source: bytes) -> list[str]:
        imports: list[str] = []
        for child in node.children:
            if child.type == "import_spec":
                path_node = child.child_by_field_name("path")
                if path_node:
                    imports.append(self._node_text(path_node, source).strip('"'))
            elif child.type == "import_spec_list":
                for spec in child.children:
                    if spec.type == "import_spec":
                        path_node = spec.child_by_field_name("path")
                        if path_node:
                            imports.append(self._node_text(path_node, source).strip('"'))
        return imports

    def _handle_type_decl(
        self, node: Node, source: bytes, file_path: str, package: str
    ) -> tuple[list[CodeElement], dict[str, CodeElement]]:
        elements: list[CodeElement] = []
        structs: dict[str, CodeElement] = {}

        for child in node.children:
            if child.type != "type_spec":
                continue
            name_node = child.child_by_field_name("name")
            type_node = child.child_by_field_name("type")
            if not name_node or not type_node:
                continue
            name = self._node_text(name_node, source)

            if type_node.type == "struct_type":
                semantic = self._go_name_role(name)
                el = CodeElement(
                    qualified_name=self._go_qualified_name(package, name, file_path),
                    kind=CodeElementKind.STRUCT,
                    file_path=file_path,
                    language="go",
                    layer=self._detect_layer(semantic, name),
                )
                elements.append(el)
                structs[name] = el

            elif type_node.type == "interface_type":
                semantic = self._go_name_role(name)
                el = CodeElement(
                    qualified_name=self._go_qualified_name(package, name, file_path),
                    kind=CodeElementKind.INTERFACE,
                    file_path=file_path,
                    language="go",
                    layer=self._detect_layer(semantic, name),
                )
                elements.append(el)
                elements.extend(
                    self._extract_interface_methods(type_node, source, file_path, package)
                )

        return elements, structs

    def _extract_interface_methods(
        self, interface_node: Node, source: bytes, file_path: str, package: str
    ) -> list[CodeElement]:
        methods: list[CodeElement] = []
        for child in interface_node.children:
            # tree-sitter-go uses "method_elem" for interface method signatures.
            if child.type not in ("method_elem", "method_spec"):
                continue
            name_node = child.child_by_field_name("name")
            if name_node is None:
                # Some versions expose the name as the first field_identifier child.
                for sub in child.children:
                    if sub.type == "field_identifier":
                        name_node = sub
                        break
            if not name_node:
                continue
            method_name = self._node_text(name_node, source)
            methods.append(
                CodeElement(
                    qualified_name=self._go_qualified_name(package, method_name, file_path),
                    kind=CodeElementKind.FUNCTION,
                    file_path=file_path,
                    language="go",
                    layer=self._detect_layer([], method_name),
                )
            )
        return methods

    def _handle_function(
        self, node: Node, source: bytes, file_path: str, package: str
    ) -> CodeElement | None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        name = self._node_text(name_node, source)
        if not name:
            return None

        semantic: list[str] = []
        if _CONTROLLER_FUNC_RE.match(name):
            semantic.append("controller")

        return CodeElement(
            qualified_name=self._go_qualified_name(package, name, file_path),
            kind=CodeElementKind.FUNCTION,
            file_path=file_path,
            language="go",
            layer=self._detect_layer(semantic, name),
        )

    def _is_http_handler(self, node: Node, source: bytes) -> bool:
        """Return True if the method has (http.ResponseWriter, *http.Request) params."""
        params_node = node.child_by_field_name("parameters")
        if not params_node:
            return False
        params_text = self._node_text(params_node, source)
        return "ResponseWriter" in params_text and "Request" in params_text

    def _get_receiver_type_name(self, node: Node, source: bytes) -> str:
        """Return the bare type name from a method receiver, e.g. 'UserHandler'."""
        receiver_node = node.child_by_field_name("receiver")
        if not receiver_node:
            return ""
        recv_text = self._node_text(receiver_node, source)
        # Strip parens and pointer stars, then take the last whitespace-delimited token.
        cleaned = recv_text.replace("*", "").strip("() ")
        parts = cleaned.split()
        return parts[-1] if parts else ""

    @staticmethod
    def _go_name_role(name: str) -> list[str]:
        """Derive role semantics from Go naming conventions."""
        if name.endswith(("Service", "Svc")):
            return ["service"]
        if name.endswith(("Repository", "Repo", "Store")):
            return ["repository"]
        return []

    @staticmethod
    def _go_qualified_name(package: str, name: str, file_path: str) -> str:
        if package:
            return f"{package}.{name}"
        import os

        base = os.path.splitext(file_path.replace("\\", "/"))[0]
        return f"{base.replace('/', '.')}.{name}"
