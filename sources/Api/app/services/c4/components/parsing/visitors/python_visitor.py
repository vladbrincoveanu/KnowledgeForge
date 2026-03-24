"""PythonVisitor: tree-sitter AST visitor for Python source files."""

from __future__ import annotations

from tree_sitter import Node, Tree

from app.services.c4.components.models import ArchitecturalLayer, CodeElement, CodeElementKind
from app.services.c4.components.parsing.visitors.base_visitor import BaseVisitor

_ROUTE_DECORATORS = frozenset({"route", "get", "post", "put", "delete", "patch"})
_DJANGO_BASE_CLASSES = ("APIView", "ViewSet", "GenericAPIView")


class PythonVisitor(BaseVisitor):
    """Extracts CodeElement objects from Python source via tree-sitter."""

    @property
    def supported_languages(self) -> list[str]:
        return ["python"]

    def visit(self, tree: Tree, file_path: str, source: bytes) -> list[CodeElement]:
        imports: list[str] = []
        call_exprs: list[str] = []
        elements: list[CodeElement] = []

        for node in tree.root_node.children:
            self._handle_node(node, source, file_path, imports, call_exprs, elements, decorators=[])

        for el in elements:
            el.imports = list(imports)
            el.method_calls = list(call_exprs)

        return elements

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        imports: list[str],
        call_exprs: list[str],
        elements: list[CodeElement],
        decorators: list[str],
    ) -> None:
        if node.type == "import_statement":
            imports.extend(self._parse_import(node, source))

        elif node.type == "import_from_statement":
            imports.extend(self._parse_import_from(node, source))

        elif node.type == "decorated_definition":
            dec_texts = self._collect_decorators(node, source)
            for child in node.children:
                if child.type in ("class_definition", "function_definition", "async_function_definition"):
                    self._handle_node(child, source, file_path, imports, call_exprs, elements, decorators=dec_texts)

        elif node.type == "class_definition":
            elements.append(self._make_class_element(node, source, file_path, decorators))

        elif node.type in ("function_definition", "async_function_definition"):
            elements.append(self._make_function_element(node, source, file_path, decorators))

        elif node.type == "expression_statement":
            self._extract_call_exprs(node, source, imports, call_exprs)

    def _parse_import(self, node: Node, source: bytes) -> list[str]:
        return [
            self._node_text(child, source)
            for child in node.children
            if child.type == "dotted_name"
        ]

    def _extract_call_exprs(
        self,
        node: Node,
        source: bytes,
        imports: list[str],
        call_exprs: list[str],
    ) -> None:
        for child in node.children:
            if child.type == "call":
                callee_text = self._get_call_callee(child, source)
                if callee_text and "." in callee_text:
                    call_exprs.append(callee_text)

    def _get_call_callee(self, node: Node, source: bytes) -> str:
        for child in node.children:
            if child.type == "attribute":
                obj = self._node_text(child.children[0], source) if child.children else ""
                attr = self._node_text(child.children[-1], source) if len(child.children) > 1 else ""
                if obj and attr:
                    return f"{obj}.{attr}"
            elif child.type == "identifier":
                return self._node_text(child, source)
        return ""

    def _parse_import_from(self, node: Node, source: bytes) -> list[str]:
        module = ""
        names: list[str] = []
        for child in node.children:
            if child.type == "dotted_name" and not module:
                module = self._node_text(child, source)
            elif child.type in ("dotted_name", "identifier") and module:
                names.append(self._node_text(child, source))
            elif child.type == "import_from_as_clause":
                for sub in child.children:
                    if sub.type in ("dotted_name", "identifier") and sub.is_named:
                        names.append(self._node_text(sub, source))
                        break
        if not names:
            return [module] if module else []
        return [f"{module}.{n}" for n in names]

    def _collect_decorators(self, decorated_node: Node, source: bytes) -> list[str]:
        texts: list[str] = []
        for child in decorated_node.children:
            if child.type == "decorator":
                texts.append(self._node_text(child, source))
        return texts

    def _make_class_element(
        self, node: Node, source: bytes, file_path: str, decorators: list[str]
    ) -> CodeElement:
        name = self._get_name(node, source)
        annotations = list(decorators)
        base_classes = self._get_base_class_names(node, source)

        for base in base_classes:
            if any(dj in base for dj in _DJANGO_BASE_CLASSES):
                annotations.append("controller")

        layer = self._detect_layer(annotations, name)
        return CodeElement(
            qualified_name=self._qualified_name(file_path, name),
            kind=CodeElementKind.CLASS,
            file_path=file_path,
            language="python",
            annotations=annotations,
            base_classes=base_classes,
            layer=layer,
        )

    def _make_function_element(
        self, node: Node, source: bytes, file_path: str, decorators: list[str]
    ) -> CodeElement:
        name = self._get_name(node, source)
        annotations = list(decorators)

        for dec in decorators:
            dec_lower = dec.lower()
            if any(r in dec_lower for r in _ROUTE_DECORATORS):
                annotations.append("route")
                break

        layer = self._detect_layer(annotations, name)
        return CodeElement(
            qualified_name=self._qualified_name(file_path, name),
            kind=CodeElementKind.FUNCTION,
            file_path=file_path,
            language="python",
            annotations=annotations,
            layer=layer,
        )

    def _get_name(self, node: Node, source: bytes) -> str:
        for child in node.children:
            if child.type == "identifier":
                return self._node_text(child, source)
        return ""

    def _get_base_class_names(self, node: Node, source: bytes) -> list[str]:
        names: list[str] = []
        for child in node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type in ("identifier", "attribute"):
                        names.append(self._node_text(arg, source))
        return names
