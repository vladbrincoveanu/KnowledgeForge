"""ElementRegistry: deduplication and architectural filtering of CodeElements."""

from __future__ import annotations

import fnmatch

from app.services.c4.components.models import ArchitecturalLayer, CodeElement

# File-path glob patterns that identify generated source files.
_GENERATED_PATTERNS: tuple[str, ...] = (
    "*_pb2.py",       # protobuf Python
    "*_pb2_grpc.py",  # protobuf gRPC stubs
    "*.generated.*",  # e.g. foo.generated.ts / foo.generated.cs
    "*.g.cs",         # Roslyn source generators
    "*.designer.cs",  # Windows Forms designer files
)


def _is_generated(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    filename = normalized.rsplit("/", 1)[-1]
    for pattern in _GENERATED_PATTERNS:
        if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def _is_data_only(el: CodeElement) -> bool:
    """Return True when >70% of members are fields and method count < 3."""
    field_count = el.metadata.get("field_count")
    method_count = el.metadata.get("method_count")
    if field_count is None or method_count is None:
        return False
    total = field_count + method_count
    if total == 0:
        return False
    field_ratio = field_count / total
    return field_ratio > 0.70 and method_count < 3


def _is_all_static(el: CodeElement) -> bool:
    return bool(el.metadata.get("all_static", False))


def _filter_reason(el: CodeElement) -> str:
    """Return a non-empty reason string if *el* should be filtered, else ''."""
    if _is_generated(el.file_path):
        return "generated code"
    if _is_data_only(el):
        return "data-only class"
    if _is_all_static(el):
        return "all-static utility class"
    return ""


def _richness(el: CodeElement) -> int:
    """Numeric score representing metadata completeness."""
    score = (
        len(el.annotations)
        + len(el.imports)
        + len(el.base_classes)
        + len(el.method_calls)
        + len(el.metadata)
        + (1 if el.role else 0)
        + (1 if el.layer != ArchitecturalLayer.UNKNOWN else 0)
    )
    return score


class ElementRegistry:
    """Collects CodeElements from multiple visitors, deduplicates, and flags
    non-architectural elements without discarding them.

    Usage::

        registry = ElementRegistry()
        registry.add_elements(visitor_a.visit(...))
        registry.add_elements(visitor_b.visit(...))

        all_elements = registry.get_all()                    # includes flagged
        arch_elements = registry.get_architectural_elements() # excludes flagged
    """

    def __init__(self) -> None:
        # qualified_name → CodeElement (richest seen so far)
        self._store: dict[str, CodeElement] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_elements(self, elements: list[CodeElement]) -> None:
        """Merge *elements* into the registry, keeping the richest copy of
        each unique ``qualified_name``."""
        for el in elements:
            existing = self._store.get(el.qualified_name)
            if existing is None or _richness(el) > _richness(existing):
                self._store[el.qualified_name] = el

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_all(self) -> list[CodeElement]:
        """Return all registered elements, applying filter flags in-place."""
        for el in self._store.values():
            reason = _filter_reason(el)
            el.filtered = bool(reason)
            el.filter_reason = reason
        return list(self._store.values())

    def get_architectural_elements(self) -> list[CodeElement]:
        """Return only elements that are *not* flagged as non-architectural."""
        return [el for el in self.get_all() if not el.filtered]
