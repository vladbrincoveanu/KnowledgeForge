from __future__ import annotations

import logging
import os
from itertools import islice
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

# Config via environment variables (keeps dependency small)
MAX_FILES_PER_GLOB = int(os.getenv("KF_MAX_FILES_PER_GLOB", os.getenv("MAX_FILES_PER_GLOB", "5000")))
MAX_TRAVERSAL_DEPTH = int(os.getenv("KF_MAX_TRAVERSAL_DEPTH", os.getenv("MAX_TRAVERSAL_DEPTH", "10")))


def limited_rglob(path: Path, pattern: str, max_files: int | None = None, max_depth: int | None = None) -> Iterator[Path]:
    """Yield files matching pattern under path but enforce limits.

    - max_files: stop after yielding this many files
    - max_depth: relative depth from `path` (0 means only top-level)

    This prevents unbounded traversal on large repositories.
    """
    max_files = MAX_FILES_PER_GLOB if max_files is None else max_files
    max_depth = MAX_TRAVERSAL_DEPTH if max_depth is None else max_depth

    base_depth = len(path.parts)
    yielded = 0

    try:
        for p in path.rglob(pattern):
            # enforce depth
            if len(p.parts) - base_depth > max_depth:
                continue
            yield p
            yielded += 1
            if yielded >= max_files:
                logger.warning(
                    "limited_rglob: reached max_files=%s for pattern=%s under %s",
                    max_files,
                    pattern,
                    path,
                )
                break
    except Exception as e:
        logger.debug("limited_rglob: traversal error for %s: %s", path, e)
        return
