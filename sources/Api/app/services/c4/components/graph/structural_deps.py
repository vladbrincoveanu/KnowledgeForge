"""StructuralDependencyAnalyzer: resolves CodeElement fields into DependencyEdges."""

from __future__ import annotations

import re

from app.services.c4.components.models import CodeElement, DependencyEdge, DependencyType

_INJECT_PATTERN = re.compile(r"inject|autowired", re.IGNORECASE)
_CAPITAL_WORD = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\b")


class StructuralDependencyAnalyzer:
    """Analyzes a list of CodeElements and produces DependencyEdges."""

    @staticmethod
    def _normalize(name: str) -> str:
        """Lowercase and strip underscores for fuzzy matching (e.g. BaseService → baseservice = base_service)."""
        return name.lower().replace("_", "")

    def analyze(self, elements: list[CodeElement]) -> list[DependencyEdge]:
        by_qualified: dict[str, CodeElement] = {el.qualified_name: el for el in elements}
        by_simple: dict[str, list[CodeElement]] = {}
        by_normalized: dict[str, list[CodeElement]] = {}
        for el in elements:
            simple = el.qualified_name.rsplit(".", 1)[-1]
            by_simple.setdefault(simple, []).append(el)
            by_normalized.setdefault(self._normalize(simple), []).append(el)

        edges: list[DependencyEdge] = []
        seen: set[tuple[str, str, DependencyType]] = set()

        for el in elements:
            src = el.qualified_name

            for token in el.imports:
                self._add_edge(src, token, DependencyType.IMPORT, 1.0, by_qualified, by_simple, by_normalized, edges, seen)

            for token in el.base_classes:
                self._add_edge(src, token, DependencyType.INHERITANCE, 2.0, by_qualified, by_simple, by_normalized, edges, seen)

            for token in el.method_calls:
                self._add_edge(src, token, DependencyType.CALL, 1.5, by_qualified, by_simple, by_normalized, edges, seen)

            for annotation in el.annotations:
                if _INJECT_PATTERN.search(annotation):
                    for word in _CAPITAL_WORD.findall(annotation):
                        self._add_edge(src, word, DependencyType.INJECTION, 2.0, by_qualified, by_simple, by_normalized, edges, seen)

        return edges

    def _add_edge(
        self,
        source: str,
        token: str,
        dep_type: DependencyType,
        weight: float,
        by_qualified: dict[str, CodeElement],
        by_simple: dict[str, list[CodeElement]],
        by_normalized: dict[str, list[CodeElement]],
        edges: list[DependencyEdge],
        seen: set[tuple[str, str, DependencyType]],
    ) -> None:
        target = self._resolve(token, by_qualified, by_simple, by_normalized)
        if target is None or target == source:
            return
        key = (source, target, dep_type)
        if key in seen:
            return
        seen.add(key)
        edges.append(DependencyEdge(source=source, target=target, dependency_type=dep_type, weight=weight))

    def _resolve(
        self,
        token: str,
        by_qualified: dict[str, CodeElement],
        by_simple: dict[str, list[CodeElement]],
        by_normalized: dict[str, list[CodeElement]],
    ) -> str | None:
        if token in by_qualified:
            return token
        simple = token.rsplit(".", 1)[-1]
        matches = by_simple.get(simple, [])
        if not matches:
            matches = by_normalized.get(self._normalize(simple), [])
        if len(matches) == 1:
            return matches[0].qualified_name
        return None
