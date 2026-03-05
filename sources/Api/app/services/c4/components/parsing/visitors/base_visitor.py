"""Abstract base visitor for tree-sitter AST traversal producing CodeElement objects."""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod

from tree_sitter import Node, Tree

from app.services.c4.components.models import ArchitecturalLayer, CodeElement

_LAYER_PATTERNS: list[tuple[re.Pattern[str], ArchitecturalLayer]] = [
    (re.compile(r"controller|handler|route|endpoint"), ArchitecturalLayer.PRESENTATION),
    (re.compile(r"service|usecase|use_case|interactor"), ArchitecturalLayer.BUSINESS),
    (re.compile(r"repository|dao|store|gateway"), ArchitecturalLayer.DATA_ACCESS),
    (re.compile(r"config|middleware|interceptor"), ArchitecturalLayer.INFRASTRUCTURE),
]


class BaseVisitor(ABC):
    """ABC for language-specific AST visitors."""

    @abstractmethod
    def visit(self, tree: Tree, file_path: str, source: bytes) -> list[CodeElement]:
        """Walk *tree* and return extracted code elements."""

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Language identifiers this visitor handles (e.g. ``["python"]``)."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _node_text(node: Node, source: bytes) -> str:
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    @staticmethod
    def _qualified_name(file_path: str, element_name: str, package: str = "") -> str:
        normalized = file_path.replace("\\", "/")
        _, ext = os.path.splitext(normalized)

        if ext == ".py":
            base = normalized[: -len(".py")]
            module = base.replace("/", ".")
            return f"{module}.{element_name}"

        if ext == ".java":
            if package:
                return f"{package}.{element_name}"
            base = os.path.splitext(normalized)[0]
            return f"{base.replace('/', '.')}.{element_name}"

        base = os.path.splitext(normalized)[0]
        return f"{base.replace('/', '.')}.{element_name}"

    @staticmethod
    def _detect_layer(annotations: list[str], name: str) -> ArchitecturalLayer:
        combined = " ".join(annotations + [name]).lower()
        for pattern, layer in _LAYER_PATTERNS:
            if pattern.search(combined):
                return layer
        return ArchitecturalLayer.UNKNOWN
