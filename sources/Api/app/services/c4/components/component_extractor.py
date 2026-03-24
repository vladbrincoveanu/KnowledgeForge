import logging
from pathlib import Path
from typing import Any, Optional

from app.services.c4.components.parsing.source_reader import SourceReader
from app.services.c4.components.parsing.tree_sitter_parser import TreeSitterParser
from app.services.c4.components.parsing.visitors.python_visitor import PythonVisitor
from app.services.c4.components.parsing.visitors.csharp_visitor import CSharpVisitor
from app.services.c4.components.parsing.visitors.go_visitor import GoVisitor
from app.services.c4.components.parsing.visitors.java_visitor import JavaVisitor
from app.services.c4.components.parsing.visitors.typescript_visitor import TypeScriptVisitor
from app.services.c4.components.graph.structural_deps import StructuralDependencyAnalyzer
from app.services.c4.components.graph.directory_deps import DirectoryDependencyAnalyzer
from app.services.c4.components.graph.dependency_graph import DependencyGraphBuilder
from app.services.c4.components.grouping.grouping_strategy import GroupingStrategy
from app.services.c4.components.models import CodeElement, ComponentObject

logger = logging.getLogger(__name__)

_VISITORS: dict = {}
for _v in [PythonVisitor(), CSharpVisitor(), GoVisitor(), JavaVisitor(), TypeScriptVisitor()]:
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
        return components
