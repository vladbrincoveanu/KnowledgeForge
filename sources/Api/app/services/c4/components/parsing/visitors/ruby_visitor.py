"""RubyVisitor: tree-sitter AST visitor for Ruby source files."""

from __future__ import annotations

from tree_sitter import Node, Tree

from app.services.c4.components.models import ArchitecturalLayer, CodeElement, CodeElementKind
from app.services.c4.components.parsing.visitors.base_visitor import BaseVisitor

_SUPERCLASS_LAYER: dict[str, ArchitecturalLayer] = {
    "applicationcontroller": ArchitecturalLayer.PRESENTATION,
    "actioncontroller::base": ArchitecturalLayer.PRESENTATION,
    "actioncontroller::api": ArchitecturalLayer.PRESENTATION,
}

_INCLUDE_ANNOTATIONS: dict[str, str] = {
    "sidekiq::worker": "worker",
    "sidekiq::job": "worker",
    "activejob::base": "worker",
}


class RubyVisitor(BaseVisitor):
    """Extracts CodeElement objects from Ruby source via tree-sitter.

    Covers class and module declarations at file scope and one level inside
    a wrapping module (the common Rails namespace pattern).
    Method extraction is intentionally omitted — the class is the right
    C4 component unit for Rails/Sidekiq codebases.
    """

    @property
    def supported_languages(self) -> list[str]:
        return ["ruby"]

    def visit(self, tree: Tree, file_path: str, source: bytes) -> list[CodeElement]:
        imports: list[str] = []
        elements: list[CodeElement] = []

        for node in tree.root_node.children:
            self._handle_top(node, source, file_path, imports, elements)

        for el in elements:
            el.imports = list(imports)

        return elements

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def _handle_top(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        imports: list[str],
        elements: list[CodeElement],
    ) -> None:
        if node.type == "class":
            el = self._make_class_element(node, source, file_path)
            if el:
                elements.append(el)

        elif node.type == "module":
            el = self._make_module_element(node, source, file_path)
            if el:
                elements.append(el)
            # Recurse one level — Rails controllers live inside Api::V1 modules
            body = self._body_statement(node)
            if body:
                for child in body.children:
                    if child.type in ("class", "module"):
                        self._handle_top(child, source, file_path, imports, elements)

        elif node.type == "call":
            imp = self._extract_require(node, source)
            if imp:
                imports.append(imp)

    # ------------------------------------------------------------------
    # Element constructors
    # ------------------------------------------------------------------

    def _make_class_element(
        self, node: Node, source: bytes, file_path: str
    ) -> CodeElement | None:
        name = self._class_name(node, source)
        if not name:
            return None

        superclass_name = self._superclass_name(node, source)
        body = self._body_statement(node)
        includes = self._collect_includes(body, source) if body else []

        annotations = list(includes)
        if superclass_name:
            annotations.append(superclass_name)

        layer = self._ruby_layer(annotations, name, superclass_name)
        return CodeElement(
            qualified_name=self._qualified_name(file_path, name),
            kind=CodeElementKind.CLASS,
            file_path=file_path,
            language="ruby",
            annotations=annotations,
            base_classes=[superclass_name] if superclass_name else [],
            layer=layer,
        )

    def _make_module_element(
        self, node: Node, source: bytes, file_path: str
    ) -> CodeElement | None:
        name = self._class_name(node, source)
        if not name:
            return None
        layer = self._detect_layer([], name)
        return CodeElement(
            qualified_name=self._qualified_name(file_path, name),
            kind=CodeElementKind.MODULE,
            file_path=file_path,
            language="ruby",
            annotations=[],
            layer=layer,
        )

    # ------------------------------------------------------------------
    # AST helpers
    # ------------------------------------------------------------------

    def _class_name(self, node: Node, source: bytes) -> str:
        for child in node.children:
            if child.type == "constant":
                return self._node_text(child, source)
            if child.type == "scope_resolution":
                # e.g. ActivityPub::ProcessingWorker — return the full scoped name
                return self._node_text(child, source)
        return ""

    def _superclass_name(self, node: Node, source: bytes) -> str:
        for child in node.children:
            if child.type == "superclass":
                for sub in child.children:
                    if sub.type in ("constant", "scope_resolution"):
                        return self._node_text(sub, source)
        return ""

    def _body_statement(self, node: Node) -> Node | None:
        for child in node.children:
            if child.type == "body_statement":
                return child
        return None

    def _collect_includes(self, body: Node, source: bytes) -> list[str]:
        """Return mixin names from `include SomeMixin` calls in a class body."""
        names: list[str] = []
        for child in body.children:
            if child.type == "call":
                fn_node = child.child_by_field_name("method")
                if fn_node and self._node_text(fn_node, source) == "include":
                    args = child.child_by_field_name("arguments")
                    if args:
                        for arg in args.children:
                            if arg.type in ("constant", "scope_resolution"):
                                names.append(self._node_text(arg, source))
        return names

    def _extract_require(self, node: Node, source: bytes) -> str:
        """Extract the string argument from `require` / `require_relative` calls."""
        fn_node = node.child_by_field_name("method")
        if fn_node is None:
            return ""
        fn_name = self._node_text(fn_node, source)
        if fn_name not in ("require", "require_relative"):
            return ""
        args = node.child_by_field_name("arguments")
        if args:
            for arg in args.children:
                if arg.type == "string":
                    text = self._node_text(arg, source)
                    return text.strip("'\"")
        return ""

    def _ruby_layer(
        self, annotations: list[str], name: str, superclass: str
    ) -> ArchitecturalLayer:
        superclass_key = superclass.lower().replace(" ", "")
        if superclass_key in _SUPERCLASS_LAYER:
            return _SUPERCLASS_LAYER[superclass_key]

        for ann in annotations:
            ann_key = ann.lower().replace(" ", "")
            if ann_key in _INCLUDE_ANNOTATIONS:
                return ArchitecturalLayer.BUSINESS

        return self._detect_layer(annotations, name)
