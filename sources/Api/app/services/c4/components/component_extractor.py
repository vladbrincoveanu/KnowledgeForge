import logging
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from app.services.c4.components.parsing.source_reader import SourceReader
from app.services.c4.components.parsing.tree_sitter_parser import TreeSitterParser
from app.services.c4.components.parsing.visitors.python_visitor import PythonVisitor
from app.services.c4.components.parsing.visitors.csharp_visitor import CSharpVisitor
from app.services.c4.components.parsing.visitors.go_visitor import GoVisitor
from app.services.c4.components.parsing.visitors.java_visitor import JavaVisitor
from app.services.c4.components.parsing.visitors.typescript_visitor import TypeScriptVisitor
from app.services.c4.components.parsing.visitors.ruby_visitor import RubyVisitor
from app.services.c4.components.graph.structural_deps import StructuralDependencyAnalyzer
from app.services.c4.components.graph.directory_deps import DirectoryDependencyAnalyzer
from app.services.c4.components.graph.dependency_graph import DependencyGraphBuilder
from app.services.c4.components.grouping.grouping_strategy import GroupingStrategy
from app.services.c4.components.models import (
    CodeElement,
    ComponentObject,
    ComponentRelationship,
    DependencyEdge,
)

# Maps structural edge types to C4-appropriate verb-phrase labels.
_DEPENDENCY_LABELS: dict[str, str] = {
    "import": "imports",
    "call": "calls",
    "inheritance": "extends",
    "injection": "uses",
}

logger = logging.getLogger(__name__)

_VISITORS: dict = {}
for _v in [PythonVisitor(), CSharpVisitor(), GoVisitor(), JavaVisitor(), TypeScriptVisitor(), RubyVisitor()]:
    for _lang in _v.supported_languages:
        _VISITORS[_lang] = _v


class ComponentExtractor:
    def __init__(self, llm_service=None, config=None) -> None:
        self._llm = llm_service
        self._parser = TreeSitterParser()
        self._source_reader = SourceReader(parser=self._parser)
        self._structural = StructuralDependencyAnalyzer()
        self._directory = DirectoryDependencyAnalyzer()
        self._graph_builder = DependencyGraphBuilder()
        self._strategy = GroupingStrategy(llm_service=llm_service, source_reader=self._source_reader)
        self._last_structural_edges: list[DependencyEdge] = []

    def extract_multi(
        self,
        roots: list[str],
        container_info: Optional[dict[str, Any]] = None,
    ) -> list[ComponentObject]:
        """Extract from multiple root directories with shared edge visibility.

        Unlike calling extract() once per root, this combines all parsed elements
        before building the dependency graph.  Cross-root imports (e.g. Polylith
        bricks that import from sibling bricks) therefore appear in the structural
        edge set and produce component-level relationships.

        Grouping uses Louvain community detection (no per-root LLM source reading)
        because there is no single container_path.  The caller is expected to run
        an LLM rename pass on the returned components.
        """
        # Phase A — Parse all roots combined
        elements_by_qname: dict[str, CodeElement] = {}
        for root in roots:
            parsed_files = self._parser.parse_directory(root)
            for pf in parsed_files:
                visitor = _VISITORS.get(pf.language)
                if visitor is None:
                    continue
                source = open(pf.file_path, "rb").read()
                for el in visitor.visit(pf.tree, pf.file_path, source):
                    elements_by_qname.setdefault(el.qualified_name, el)

        elements = list(elements_by_qname.values())
        logger.info(
            "extract_multi Phase A: %d roots → %d elements", len(roots), len(elements)
        )

        if not elements:
            return []

        # Phase B — Graph (cross-root edges now visible)
        structural_edges = self._structural.analyze(elements)
        directory_edges = self._directory.analyze(elements, existing_edges=structural_edges)
        dep_graph = self._graph_builder.build(elements, structural_edges, directory_edges)
        summary = DependencyGraphBuilder.summary(dep_graph)
        logger.info(
            "extract_multi Phase B: %d nodes, %d edges", summary["nodes"], summary["edges"]
        )

        # Phase C — Group (no container_path → Louvain fallback, caller renames)
        components = self._strategy.group(
            elements,
            dep_graph,
            container_path=None,
            container_info=container_info,
        )
        logger.info("extract_multi Phase C: %d components", len(components))

        # Store edges so the caller can lift relationships after post-processing
        # (merging and renaming change component names, so lifting must happen last).
        self._last_structural_edges = structural_edges

        return components

    def extract(
        self,
        container_root_path: str,
        container_info: Optional[dict[str, Any]] = None,
    ) -> list[ComponentObject]:
        container_path = Path(container_root_path)

        # Phase A — Parse
        parsed_files = self._parser.parse_directory(str(container_path))
        elements_by_qname: dict[str, CodeElement] = {}
        for pf in parsed_files:
            visitor = _VISITORS.get(pf.language)
            if visitor is None:
                continue
            source = open(pf.file_path, "rb").read()
            for el in visitor.visit(pf.tree, pf.file_path, source):
                elements_by_qname.setdefault(el.qualified_name, el)
        elements = list(elements_by_qname.values())
        logger.info("Phase A: parsed %d files, extracted %d elements", len(parsed_files), len(elements))

        if not elements:
            return []

        # Phase B — Graph
        structural_edges = self._structural.analyze(elements)
        directory_edges = self._directory.analyze(elements, existing_edges=structural_edges)
        dep_graph = self._graph_builder.build(elements, structural_edges, directory_edges)
        summary = DependencyGraphBuilder.summary(dep_graph)
        logger.info("Phase B: graph with %d nodes, %d edges", summary["nodes"], summary["edges"])

        # Phase C — Group
        components = self._strategy.group(
            elements,
            dep_graph,
            container_path=container_path,
            container_info=container_info,
        )
        logger.info("Phase C: found %d components", len(components))

        # Store edges so the caller can lift relationships after post-processing.
        # Merging and renaming passes in the caller change component names, so
        # relationship lifting must happen after those passes, not here.
        self._last_structural_edges = structural_edges

        return components


def _lift_structural_relationships(
    components: list[ComponentObject],
    structural_edges: list[DependencyEdge],
) -> int:
    """Populate ComponentObject.relationships from element-level structural edges.

    One ComponentRelationship is produced per ordered component pair, labelled
    by the dominant edge type across all element-level edges between that pair.
    Mutates components in place. Returns the number of relationships added.
    """
    if not components or not structural_edges:
        return 0

    el_to_comp: dict[str, ComponentObject] = {
        el.qualified_name: comp
        for comp in components
        for el in comp.code_elements
    }
    comp_by_id: dict[str, ComponentObject] = {c.component_id: c for c in components}

    # Aggregate edge-type counts per (source_component_id, target_component_id) pair.
    pair_type_counts: dict[tuple[str, str], Counter] = {}
    for edge in structural_edges:
        src_comp = el_to_comp.get(edge.source)
        tgt_comp = el_to_comp.get(edge.target)
        if src_comp is None or tgt_comp is None or src_comp is tgt_comp:
            continue
        pair = (src_comp.component_id, tgt_comp.component_id)
        if pair not in pair_type_counts:
            pair_type_counts[pair] = Counter()
        pair_type_counts[pair][edge.dependency_type.value] += 1

    count = 0
    for (src_id, tgt_id), type_counts in pair_type_counts.items():
        src_comp = comp_by_id.get(src_id)
        tgt_comp = comp_by_id.get(tgt_id)
        if src_comp is None or tgt_comp is None:
            continue
        dominant = type_counts.most_common(1)[0][0]
        label = _DEPENDENCY_LABELS.get(dominant, "uses")
        src_comp.relationships.append(
            ComponentRelationship(
                source_component=src_comp.name,
                target_component=tgt_comp.name,
                label=label,
            )
        )
        count += 1
    return count
