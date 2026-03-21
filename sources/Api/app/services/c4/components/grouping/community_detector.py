"""Louvain community detection fallback for grouping ungrouped CodeElements."""

from __future__ import annotations

import hashlib
import os
import re
from collections import Counter, defaultdict

import community as community_louvain
import networkx as nx

from app.services.c4.components.models import (
    ArchitecturalLayer,
    CodeElement,
    ComponentObject,
    ExtractionMethod,
)

_GENERIC_TOKENS = frozenset({
    "impl", "base", "util", "service", "helper", "handler",
    "manager", "factory", "builder", "abstract", "common",
    # Java/C# package prefixes and ubiquitous tokens
    "com", "org", "net", "main", "app", "src", "lib", "pkg",
    "internal", "model", "models", "config", "test", "tests",
    "core", "server", "client", "program", "startup", "index",
    "users", "module", "modules", "controllers", "services",
    "repositories", "api", "web", "data",
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

        base_name: str | None = None

        # --- Directory strategy ---
        dir_names: list[str] = []
        for e in elements:
            parent = os.path.basename(os.path.dirname(e.file_path))
            if parent:
                dir_names.append(parent.lower())

        if dir_names:
            dir_counter = Counter(dir_names)
            most_common_dir, dir_count = dir_counter.most_common(1)[0]
            # Only use directory name when it actually discriminates among
            # elements.  When every element lives in the same directory (e.g.
            # the container root) the name carries no information.
            has_variety = len(dir_counter) > 1
            # Skip directory names that look like project/container roots
            # (contain hyphens, e.g. "omnipay-settlement-orchestrator").
            looks_like_project = "-" in most_common_dir
            if has_variety and not looks_like_project and dir_count / len(elements) > 0.5 and len(most_common_dir) > 2:
                base_name = most_common_dir.capitalize()

        # --- Symbol-name token strategy ---
        # Use only the leaf symbol name (class/function), not path segments
        # which pollute with directory names and usernames.
        if base_name is None:
            tokens: list[str] = []
            for e in elements:
                # Last segment of qualified name is the symbol itself
                symbol = e.qualified_name.rsplit(".", 1)[-1]
                # Split CamelCase and snake_case into meaningful tokens
                parts = re.sub(r"([a-z])([A-Z])", r"\1_\2", symbol).split("_")
                for part in parts:
                    token = part.lower()
                    if len(token) > 2 and token not in _GENERIC_TOKENS:
                        tokens.append(token)

            if tokens:
                most_common_token, _ = Counter(tokens).most_common(1)[0]
                base_name = most_common_token.capitalize()

        # --- Fallback: stable hash of sorted element names ---
        if base_name is None:
            key = "_".join(sorted(e.qualified_name for e in elements))
            short_hash = hashlib.md5(key.encode()).hexdigest()[:4]
            return f"Component_{short_hash}"

        suffix = self._layer_suffix(elements)
        if suffix and not base_name.lower().endswith(suffix.lower()):
            return f"{base_name}{suffix}"
        return base_name

    @staticmethod
    def _layer_suffix(elements: list[CodeElement]) -> str:
        """Return a role suffix based on the dominant architectural layer."""
        layer_counts = Counter(
            e.layer for e in elements if e.layer != ArchitecturalLayer.UNKNOWN
        )
        if not layer_counts:
            return ""
        dominant = layer_counts.most_common(1)[0][0]
        return {
            ArchitecturalLayer.PRESENTATION: "API",
            ArchitecturalLayer.BUSINESS: "Service",
            ArchitecturalLayer.DATA_ACCESS: "Repository",
            ArchitecturalLayer.INFRASTRUCTURE: "Infrastructure",
        }.get(dominant, "")

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
