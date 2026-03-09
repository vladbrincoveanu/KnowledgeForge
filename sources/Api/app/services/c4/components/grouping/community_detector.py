"""Louvain community detection fallback for grouping ungrouped CodeElements."""

from __future__ import annotations

import hashlib
import os
from collections import Counter, defaultdict

import community as community_louvain
import networkx as nx

from app.services.c4.components.models import (
    CodeElement,
    ComponentObject,
    ExtractionMethod,
)

_GENERIC_TOKENS = frozenset({
    "impl", "base", "util", "service", "helper", "handler",
    "manager", "factory", "builder", "abstract", "common",
})


class CommunityDetector:
    """Groups CodeElements into ComponentObjects using Louvain community detection."""

    def detect(
        self,
        graph: nx.Graph,
        min_size: int = 2,
        resolution: float = 1.0,
    ) -> dict[str, int]:
        """Return partition dict {node_name: cluster_id}.

        Falls back to one-cluster-per-node when graph has no edges.
        """
        if graph.number_of_nodes() == 0:
            return {}
        if graph.number_of_edges() == 0:
            return {node: i for i, node in enumerate(graph.nodes())}
        return community_louvain.best_partition(
            graph, weight="weight", resolution=resolution
        )

    def post_process(
        self,
        partition: dict[str, int],
        graph: nx.Graph,
        min_size: int = 2,
        max_size: int = 15,
    ) -> dict[str, int]:
        """Merge singletons and split oversized clusters.

        Returns an updated partition dict.
        """
        partition = dict(partition)

        # --- Merge singletons ---
        cluster_members: dict[int, list[str]] = defaultdict(list)
        for node, cid in partition.items():
            cluster_members[cid].append(node)

        for cid, members in list(cluster_members.items()):
            if len(members) < min_size:
                for node in members:
                    # Find neighbor with highest edge weight
                    best_neighbor: str | None = None
                    best_weight: float = -1.0
                    for neighbor in graph.neighbors(node):
                        if neighbor == node:
                            continue
                        w = graph[node][neighbor].get("weight", 1.0)
                        if w > best_weight:
                            best_weight = w
                            best_neighbor = neighbor
                    if best_neighbor is not None:
                        partition[node] = partition[best_neighbor]
                    else:
                        partition[node] = 0

        # --- Split oversized clusters ---
        # Recompute cluster_members after singleton merging
        cluster_members = defaultdict(list)
        for node, cid in partition.items():
            cluster_members[cid].append(node)

        next_id = max(partition.values(), default=0) + 1

        for cid, members in list(cluster_members.items()):
            if len(members) <= max_size:
                continue
            subgraph = graph.subgraph(members).copy()
            if subgraph.number_of_edges() > 0:
                sub_partition = community_louvain.best_partition(subgraph, weight="weight")
            else:
                # No edges — each connected component becomes its own sub-cluster
                sub_partition = {}
                for comp_id, component in enumerate(nx.connected_components(subgraph)):
                    for node in component:
                        sub_partition[node] = comp_id

            # Map sub-cluster ids to globally unique ids
            sub_id_map: dict[int, int] = {}
            for node, sub_cid in sub_partition.items():
                if sub_cid not in sub_id_map:
                    sub_id_map[sub_cid] = next_id
                    next_id += 1
                partition[node] = sub_id_map[sub_cid]

        return partition

    def partition_to_groups(
        self,
        partition: dict[str, int],
        elements: list[CodeElement],
    ) -> list[list[CodeElement]]:
        """Group CodeElements by cluster id from partition.

        Elements not present in the partition are excluded.
        """
        name_to_element: dict[str, CodeElement] = {
            e.qualified_name: e for e in elements
        }

        cluster_elements: dict[int, list[CodeElement]] = defaultdict(list)
        for node, cid in partition.items():
            if node in name_to_element:
                cluster_elements[cid].append(name_to_element[node])

        return list(cluster_elements.values())

    def name_cluster(self, elements: list[CodeElement]) -> str:
        """Derive a human-readable name for a cluster of elements."""
        if not elements:
            return "Component"

        # --- Directory strategy ---
        dir_names: list[str] = []
        for e in elements:
            parent = os.path.basename(os.path.dirname(e.file_path))
            if parent:
                dir_names.append(parent.lower())

        if dir_names:
            most_common_dir, dir_count = Counter(dir_names).most_common(1)[0]
            if dir_count / len(elements) > 0.5 and len(most_common_dir) > 2:
                return most_common_dir.capitalize()

        # --- Qualified-name token strategy ---
        tokens: list[str] = []
        for e in elements:
            for part in e.qualified_name.replace("_", ".").split("."):
                token = part.lower()
                if len(token) > 2 and token not in _GENERIC_TOKENS:
                    tokens.append(token)

        if tokens:
            most_common_token, _ = Counter(tokens).most_common(1)[0]
            return most_common_token.capitalize()

        # --- Fallback: stable hash of sorted element names ---
        key = "_".join(sorted(e.qualified_name for e in elements))
        short_hash = hashlib.md5(key.encode()).hexdigest()[:4]
        return f"Component_{short_hash}"

    def to_components(
        self, groups: list[list[CodeElement]]
    ) -> list[ComponentObject]:
        """Convert element groups to ComponentObjects."""
        components: list[ComponentObject] = []
        for group in groups:
            if not group:
                continue
            name = self.name_cluster(group)
            component_id = f"community_{name.lower()}"
            components.append(
                ComponentObject(
                    component_id=component_id,
                    name=name,
                    extraction_method=ExtractionMethod.COMMUNITY_DETECTION,
                    confidence=0.6,
                    code_elements=group,
                )
            )
        return components
