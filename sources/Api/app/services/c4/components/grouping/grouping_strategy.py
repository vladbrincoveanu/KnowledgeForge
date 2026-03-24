"""Orchestrates grouping: framework detection → LLM primary → Louvain fallback."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx

from app.services.c4.components.graph.dependency_graph import DependencyGraphBuilder
from app.services.c4.components.models import (
    CodeElement,
    ComponentObject,
    ExtractionMethod,
)
from app.services.c4.components.parsing.source_reader import SourceReader
from .community_detector import CommunityDetector
from .component_builder import ComponentBuilder
from .framework_detector import FrameworkDetectorRegistry

if TYPE_CHECKING:
    from app.services.c4.components.enrichment.llm_component_service import LLMComponentService

_LLM_DIRECT_THRESHOLD = 60


class GroupingStrategy:
    """Three-tier grouping orchestrator.

    Tier 1: framework detection (Spring, Django, FastAPI) — fast path, high confidence.
    Tier 2a: LLM source-code analysis (when container_path available).
    Tier 2b: LLM-element grouping (when no source access but LLM available).
    Tier 2c: Louvain community detection fallback when LLM is unavailable.
    """

    def __init__(
        self,
        registry: FrameworkDetectorRegistry | None = None,
        community_detector: CommunityDetector | None = None,
        builder: ComponentBuilder | None = None,
        llm_service: LLMComponentService | None = None,
        source_reader: SourceReader | None = None,
    ) -> None:
        self._registry = registry or FrameworkDetectorRegistry()
        self._detector = community_detector or CommunityDetector()
        self._builder = builder or ComponentBuilder()
        self._llm = llm_service
        self._source_reader = source_reader if source_reader is not None else SourceReader()

    def group(
        self,
        elements: list[CodeElement],
        dep_graph: nx.DiGraph,
        container_path: Path | None = None,
        container_info: dict[str, Any] | None = None,
    ) -> list[ComponentObject]:
        framework_components: list[ComponentObject] = []
        remainder = elements

        # Tier 1 — framework detection (fast path, confidence > 0.5)
        fw_result = self._registry.detect_with_confidence(elements)
        if fw_result:
            framework_components = fw_result[1].components
            remainder = fw_result[1].ungrouped_elements

        if not remainder:
            return framework_components

        # Tier 2: LLM available
        if self._llm is not None:
            if container_path is not None:
                # Tier 2a: LLM reads source directly — replaces classify_elements
                remainder_components = self._identify_from_source(
                    container_path,
                    container_info or {},
                    remainder,
                    already_detected=framework_components,
                )
            else:
                # Tier 2b: Fall back to element-based LLM grouping (no source access)
                remainder_components = self._group_with_llm(remainder, dep_graph)
        else:
            # Tier 3: Louvain fallback
            remainder_components = self._group_with_louvain(remainder, dep_graph)

        merged = self._merge_and_dedup(framework_components, remainder_components)
        return self._deduplicate_components(merged)

    def _merge_and_dedup(
        self,
        framework_components: list[ComponentObject],
        llm_components: list[ComponentObject],
    ) -> list[ComponentObject]:
        if not framework_components:
            return llm_components
        if not llm_components:
            return framework_components

        result: list[ComponentObject] = list(framework_components)
        fw_element_sets: list[frozenset[str]] = []
        for fw in framework_components:
            fw_elements = frozenset(e.qualified_name for e in fw.code_elements)
            fw_element_sets.append(fw_elements)

        for llm_comp in llm_components:
            llm_elements = frozenset(e.qualified_name for e in llm_comp.code_elements)
            if not llm_elements:
                result.append(llm_comp)
                continue

            overlap_found = False
            for i, fw_elements in enumerate(fw_element_sets):
                intersection = llm_elements & fw_elements
                union = llm_elements | fw_elements
                overlap_ratio = len(intersection) / len(union) if union else 0

                if overlap_ratio >= 0.7:
                    overlap_found = True
                    if len(llm_comp.description) > len(result[i].description):
                        result[i].description = llm_comp.description
                    for key, value in llm_comp.metadata.items():
                        if not result[i].metadata.get(key):
                            result[i].metadata[key] = value
                    break

            if not overlap_found:
                result.append(llm_comp)

        return result

    def _identify_from_source(
        self,
        container_path: Path,
        container_info: dict[str, Any],
        remainder: list[CodeElement],
        already_detected: list[ComponentObject],
    ) -> list[ComponentObject]:
        container_name = container_info.get("name", container_path.name)
        technology = container_info.get("technology", "")

        sources = self._source_reader.read_container_sources(str(container_path))
        components, contracts = self._llm.identify_components_and_contracts_from_source(
            container_name=container_name,
            technology=technology,
            source_files=sources.files,
            file_tree=sources.tree_summary,
            already_detected=already_detected,
            remainder=remainder,
        )

        if not components and not contracts:
            return self._group_with_louvain(remainder, None)

        # Attach contracts to their owning component's metadata so they survive the call stack.
        if contracts:
            comp_by_name = {c.name: c for c in components}
            for contract in contracts:
                owner = comp_by_name.get(contract.component)
                if owner is not None:
                    owner.metadata.setdefault("contracts", []).append(contract.model_dump())

        return components

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
        dep_graph: nx.DiGraph | None,
    ) -> list[ComponentObject]:
        if dep_graph is None:
            return [
                self._builder.build([e], ExtractionMethod.COMMUNITY_DETECTION)
                for e in remainder
                if e
            ]
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
