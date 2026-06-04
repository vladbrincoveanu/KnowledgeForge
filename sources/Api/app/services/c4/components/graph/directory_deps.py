"""DirectoryDependencyAnalyzer: produces DIRECTORY edges based on file-path proximity.

Complexity: O(D² + E_nearby) where D = number of unique directories, E_nearby = element
pairs in nearby-directory pairs.  This is dramatically faster than the naive O(n²)
element-pair approach when the codebase has many elements spread across few directories.

Large directories (>_MAX_ELEMENTS_PER_DIR) are capped so that a monorepo with hundreds
of sibling packages (e.g. connectors/source-xxx/) cannot produce millions of cross-product
edges between distance-2 directory pairs.
"""

from __future__ import annotations

import os

from app.services.c4.components.models import CodeElement, DependencyEdge, DependencyType

_DIR_WEIGHTS: dict[int, float] = {0: 0.3, 1: 0.15, 2: 0.1}
# Cross-products explode when many dirs are distance-2 siblings (e.g. connector monorepos).
# Cap each directory to this many elements before building edges.
_MAX_ELEMENTS_PER_DIR = 20


class DirectoryDependencyAnalyzer:

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()

    @staticmethod
    def _parts_distance(d1: tuple[str, ...], d2: tuple[str, ...]) -> int | None:
        """Return directory-tree distance between two pre-split dir paths, or None if > 2."""
        common = 0
        for x, y in zip(d1, d2):
            if x == y:
                common += 1
            else:
                break
        dist = (len(d1) - common) + (len(d2) - common)
        return dist if dist <= 2 else None

    def _emit(
        self,
        a: CodeElement,
        b: CodeElement,
        weight: float,
        existing: set[tuple[str, str]],
        result: list[DependencyEdge],
    ) -> None:
        for src, tgt in (
            (a.qualified_name, b.qualified_name),
            (b.qualified_name, a.qualified_name),
        ):
            pair = (src, tgt)
            if pair in existing or pair in self._seen:
                continue
            self._seen.add(pair)
            result.append(
                DependencyEdge(
                    source=src,
                    target=tgt,
                    dependency_type=DependencyType.DIRECTORY,
                    weight=weight,
                )
            )

    def analyze(
        self,
        elements: list[CodeElement],
        existing_edges: list[DependencyEdge] | None = None,
    ) -> list[DependencyEdge]:
        existing: set[tuple[str, str]] = set()
        if existing_edges:
            for e in existing_edges:
                existing.add((e.source, e.target))

        result: list[DependencyEdge] = []

        # Group elements by directory (tuple of path parts).
        # Then iterate D² directory pairs instead of n² element pairs.
        # Cap large directories so sibling-package cross-products stay bounded.
        dir_index: dict[tuple[str, ...], list[CodeElement]] = {}
        for el in elements:
            key = tuple(os.path.normpath(os.path.dirname(el.file_path)).split(os.sep))
            bucket = dir_index.setdefault(key, [])
            if len(bucket) < _MAX_ELEMENTS_PER_DIR:
                bucket.append(el)

        dirs = list(dir_index.keys())

        for i in range(len(dirs)):
            d1 = dirs[i]
            for j in range(i, len(dirs)):
                d2 = dirs[j]
                dist = self._parts_distance(d1, d2)
                if dist is None:
                    continue
                weight = _DIR_WEIGHTS[dist]
                g1 = dir_index[d1]
                g2 = dir_index[d2]
                if i == j:
                    for k in range(len(g1)):
                        for m in range(k + 1, len(g1)):
                            self._emit(g1[k], g1[m], weight, existing, result)
                else:
                    for a in g1:
                        for b in g2:
                            self._emit(a, b, weight, existing, result)

        return result
