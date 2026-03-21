"""Orchestrates grouping: framework detection → LLM primary → Louvain fallback."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import networkx as nx

from app.services.c4.components.graph.dependency_graph import DependencyGraphBuilder
from app.services.c4.components.models import (
    CodeElement,
    ComponentObject,
    ExtractionMethod,
)
from .community_detector import CommunityDetector
from .component_builder import ComponentBuilder
from .framework_detector import FrameworkDetectorRegistry

if TYPE_CHECKING:
    from app.services.c4.components.enrichment.llm_component_service import LLMComponentService

_LLM_DIRECT_THRESHOLD = 60


class GroupingStrategy:
    """Three-tier grouping orchestrator.

    Tier 1: framework detection (Spring, Django, FastAPI) — fast path, high confidence.
    Tier 2a: LLM-primary grouping of remainder (direct or Louvain-refined).
    Tier 2b: Louvain community detection fallback when LLM is unavailable.
    """

    def __init__(
        self,
        registry: FrameworkDetectorRegistry | None = None,
        community_detector: CommunityDetector | None = None,
        builder: ComponentBuilder | None = None,
        llm_service: LLMComponentService | None = None,
    ) -> None:
        self._registry = registry or FrameworkDetectorRegistry()
        self._detector = community_detector or CommunityDetector()
        self._builder = builder or ComponentBuilder()
        self._llm = llm_service

    def group(
        self,
        elements: list[CodeElement],
        dep_graph: nx.DiGraph,
    ) -> list[ComponentObject]:
        """Group elements into ComponentObjects using three-tier strategy."""
        framework_components: list[ComponentObject] = []
        remainder = elements

        # Tier 1 — framework detection (fast path, confidence > 0.5)
        fw_result = self._registry.detect_with_confidence(elements)
        if fw_result:
            framework_components = fw_result[1].components
            remainder = fw_result[1].ungrouped_elements

        if not remainder:
            return framework_components

        # Tier 2a — LLM available
        if self._llm is not None:
            remainder_components = self._group_with_llm(remainder, dep_graph)
        else:
            # Tier 2b — Louvain fallback
            remainder_components = self._group_with_louvain(remainder, dep_graph)

        return self._deduplicate_components(framework_components + remainder_components)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _group_with_llm(
        self,
        remainder: list[CodeElement],
        dep_graph: nx.DiGraph,
    ) -> list[ComponentObject]:
        classified = self._llm.classify_elements(remainder)

        if len(classified) < _LLM_DIRECT_THRESHOLD:
            components = self._llm.group_elements(classified, edges=[])
            for comp in components:
                comp.extraction_method = ExtractionMethod.LLM_DIRECT
                comp.confidence = 0.85
            return components

        # Large remainder: use Louvain to propose structure, then LLM refines
        undirected = DependencyGraphBuilder.get_undirected_weighted(dep_graph)
        names = {e.qualified_name for e in remainder}
        subgraph = undirected.subgraph(names).copy()

        partition = self._detector.detect(subgraph)
        partition = self._detector.post_process(partition, subgraph)
        louvain_groups = self._detector.partition_to_groups(partition, classified)

        components = self._llm.refine_grouping(louvain_groups, classified, edges=[])
        for comp in components:
            comp.extraction_method = ExtractionMethod.LLM_REFINED
            comp.confidence = 0.75
        return components

    @staticmethod
    def _deduplicate_components(
        components: list[ComponentObject],
    ) -> list[ComponentObject]:
        """Remove elements that appear in multiple components, keeping each only in the highest-confidence one."""
        # Map each qualified_name to all (component_index, confidence) pairs
        qname_to_entries: dict[str, list[tuple[int, float]]] = defaultdict(list)
        for idx, comp in enumerate(components):
            for element in comp.code_elements:
                qname_to_entries[element.qualified_name].append((idx, comp.confidence))

        # For duplicates, determine the winning component index (highest confidence)
        winner: dict[str, int] = {}
        for qname, entries in qname_to_entries.items():
            if len(entries) > 1:
                winner[qname] = max(entries, key=lambda x: x[1])[0]

        if not winner:
            return components

        result: list[ComponentObject] = []
        for idx, comp in enumerate(components):
            comp.code_elements = [
                e for e in comp.code_elements
                if winner.get(e.qualified_name, idx) == idx
            ]
            if comp.code_elements:
                result.append(comp)
        return result

    def _group_with_louvain(
        self,
        remainder: list[CodeElement],
        dep_graph: nx.DiGraph,
    ) -> list[ComponentObject]:
        undirected = DependencyGraphBuilder.get_undirected_weighted(dep_graph)
        names = {e.qualified_name for e in remainder}
        subgraph = undirected.subgraph(names).copy()

        partition = self._detector.detect(subgraph)
        partition = self._detector.post_process(partition, subgraph)
        groups = self._detector.partition_to_groups(partition, remainder)
        return [
            self._builder.build(g, ExtractionMethod.COMMUNITY_DETECTION)
            for g in groups
            if g
        ]
