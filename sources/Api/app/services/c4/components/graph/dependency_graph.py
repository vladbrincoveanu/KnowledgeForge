"""Builds a weighted directed graph from dependency edges for graph-algorithm-based component detection."""

from __future__ import annotations

import networkx as nx

from app.services.c4.components.models import CodeElement, DependencyEdge


class DependencyGraphBuilder:

    def build(
        self,
        elements: list[CodeElement],
        structural_edges: list[DependencyEdge],
        directory_edges: list[DependencyEdge],
        semantic_edges: list[DependencyEdge] | None = None,
    ) -> nx.DiGraph:
        """Combine all edges into a weighted DiGraph. Same source→target gets summed weights."""
        g = nx.DiGraph()
        for el in elements:
            g.add_node(el.qualified_name, element=el)
        all_edges = structural_edges + directory_edges + (semantic_edges or [])
        for edge in all_edges:
            if g.has_edge(edge.source, edge.target):
                g[edge.source][edge.target]["weight"] += edge.weight
            else:
                g.add_edge(edge.source, edge.target, weight=edge.weight)
        return g

    @staticmethod
    def get_undirected_weighted(graph: nx.DiGraph) -> nx.Graph:
        """Return undirected graph merging parallel edges by summing weights."""
        ug = nx.Graph()
        ug.add_nodes_from(graph.nodes(data=True))
        for u, v, data in graph.edges(data=True):
            w = data.get("weight", 1.0)
            if ug.has_edge(u, v):
                ug[u][v]["weight"] += w
            else:
                ug.add_edge(u, v, weight=w)
        return ug

    @staticmethod
    def get_subgraph(graph: nx.DiGraph, element_names: list[str]) -> nx.DiGraph:
        """Return an induced subgraph for the given node names."""
        return graph.subgraph(element_names).copy()

    @staticmethod
    def summary(graph: nx.DiGraph) -> dict:
        """Return basic graph statistics."""
        return {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "density": nx.density(graph),
            "weakly_connected_components": nx.number_weakly_connected_components(graph),
        }
