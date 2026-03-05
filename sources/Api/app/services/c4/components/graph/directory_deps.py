"""DirectoryDependencyAnalyzer: produces DIRECTORY edges based on file-path proximity."""

from __future__ import annotations

import os

from app.services.c4.components.models import CodeElement, DependencyEdge, DependencyType

_DIR_WEIGHTS: dict[int, float] = {0: 0.3, 1: 0.15, 2: 0.1}


class DirectoryDependencyAnalyzer:

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()

    @staticmethod
    def _dir_distance(path_a: str, path_b: str) -> int | None:
        dir_a = os.path.normpath(os.path.dirname(path_a)).split(os.sep)
        dir_b = os.path.normpath(os.path.dirname(path_b)).split(os.sep)
        common = 0
        for x, y in zip(dir_a, dir_b):
            if x == y:
                common += 1
            else:
                break
        dist = (len(dir_a) - common) + (len(dir_b) - common)
        return dist if dist <= 2 else None

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

        for i in range(len(elements)):
            for j in range(i + 1, len(elements)):
                a, b = elements[i], elements[j]
                dist = self._dir_distance(a.file_path, b.file_path)
                if dist is None:
                    continue
                weight = _DIR_WEIGHTS[dist]
                for src, tgt in ((a.qualified_name, b.qualified_name), (b.qualified_name, a.qualified_name)):
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

        return result
