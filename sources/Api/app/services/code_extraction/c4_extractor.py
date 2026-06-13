"""C4 Model-based architecture extractor.

Implements the C4 Model approach to avoid information overload:
- Level 1 (Context): System + External dependencies
- Level 2 (Container): Deployable units (services, databases, frontends)
- Level 3 (Component): Public entry points only (not internal details)

Focus on architectural boundaries, not code details.
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.services.c4.graph_writer import GraphWriter
from app.services.c4.graphify_c4_extractor import GraphifyC4Extractor
from app.infrastructure.graph.neo4j_client import Neo4jClient
from app.domain.exceptions import GraphDatabaseError
from utils.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class TimingResult:
    name: str
    duration_ms: float
    success: bool = True
    error: Optional[str] = None


@dataclass
class BenchmarkResults:
    task_id: str
    repository_url: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    total_duration_ms: float = 0.0
    phases: list[TimingResult] = field(default_factory=list)

    def add_phase(self, name: str, duration_ms: float, success: bool = True, error: Optional[str] = None):
        self.phases.append(TimingResult(name=name, duration_ms=duration_ms, success=success, error=error))
        self.total_duration_ms += duration_ms

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / f"{self.task_id}_benchmark.json"
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return filepath


class PerformanceTracker:
    def __init__(self, task_id: str, repository_url: str, output_dir: Optional[Path] = None):
        self.task_id = task_id
        self.repository_url = repository_url
        self.results = BenchmarkResults(task_id=task_id, repository_url=repository_url)
        self.output_dir = output_dir or Path("sources/data/benchmarks")

    def save(self) -> Path:
        return self.results.save(self.output_dir)


class C4ArchitectureExtractor:
    """Extract architecture using C4 Model principles.

    Philosophy:
    - Extract architectural boundaries, not code details
    - Focus on entry/exit points (APIs, databases, external services)
    - Group by domain to avoid clutter
    - Use LLM only for system summaries
    """

    def __init__(self, repo_path: Path, llm_manager=None):
        self.repo_path = Path(repo_path).resolve()

    def extract(self, max_components_per_domain: int = 10, group_components_by_domain: bool = False, task_id: Optional[str] = None, repo_url: Optional[str] = None) -> dict[str, Any]:
        """Extract C4 architecture."""
        self.task_id = task_id or f"extract_{int(time.time())}"
        tracker = PerformanceTracker(
            task_id=self.task_id,
            repository_url=repo_url or str(self.repo_path)
        )

        logger.info("Starting C4 Model extraction (Graphify + OpenRouter backend)...")
        logger.info("=" * 80)

        t0 = time.time()
        c4_architecture = GraphifyC4Extractor(self.repo_path).extract()
        extraction_ms = (time.time() - t0) * 1000
        if tracker:
            tracker.results.add_phase("Graphify_C4_Extraction", extraction_ms)

        if tracker:
            tracker.save()
            logger.info(f"\n📊 Benchmark saved: {tracker.results.task_id}_benchmark.json")

        logger.info("\n" + "=" * 80)
        logger.info("✅ C4 Model Extraction Complete (Graphify backend)")
        logger.info("=" * 80)
        sys_ctx = c4_architecture.get("system_context", {})
        logger.info(f"Level 1 (Context): system={sys_ctx.get('name', 'Unknown')}, "
                    f"{len(sys_ctx.get('external_dependencies', []))} external deps")
        logger.info(f"Level 2 (Containers): {len(c4_architecture.get('containers', []))} deployable units")
        logger.info(f"Level 3 (Components): {len(c4_architecture.get('components', []))} components")
        logger.info(f"  [{extraction_ms:.0f}ms total]")

        # Write to Neo4j (extraction fails if Neo4j unavailable)
        try:
            graph_writer = GraphWriter(Neo4jClient.from_config())
            graph_writer.write(task_id, c4_architecture)
        except GraphDatabaseError as e:
            logger.error(f"Neo4j write failed for extraction {task_id}: {e}")
            raise

        return c4_architecture

    def save(self, c4_data: dict[str, Any], output_path: Path):
        """Save C4 architecture to JSON."""
        with open(output_path, 'w') as f:
            json.dump(c4_data, f, indent=2)
        logger.info(f"C4 architecture saved to: {output_path}")
        return c4_data


def main():
    """Test C4 extractor."""
    import sys
    import os

    def find_repo_root(start: Path) -> Path:
        for parent in [start] + list(start.parents):
            if (parent / ".git").exists():
                return parent
        return start

    app_path = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(app_path))

    from infrastructure.llm.llm_manager import LLMManager

    demo_path_env = os.getenv("DEMO_REPO_PATH", "")
    if demo_path_env and Path(demo_path_env).exists():
        target_repo = Path(demo_path_env)
    else:
        repo_root = find_repo_root(app_path)
        demo_path = repo_root / "sources" / "demo"
        monorepo_path = repo_root / "monorepo"
        target_repo = demo_path if demo_path.exists() else (monorepo_path if monorepo_path.exists() else repo_root)

    try:
        config = get_config()
        provider = os.getenv(
            "LLM_PROVIDER",
            getattr(config.llm, "provider", "lmstudio") if hasattr(config, "llm") else "lmstudio",
        )
        base_url = os.getenv(
            "LLM_BASE_URL",
            getattr(config.llm, "base_url", "http://localhost:1234/v1") if hasattr(config, "llm") else "http://localhost:1234/v1",
        )
        model = os.getenv(
            "LLM_MODEL",
            getattr(config.llm, "model_name", "qwen/qwen2.5-vl-7b") if hasattr(config, "llm") else "qwen/qwen2.5-vl-7b",
        )
        api_key = os.getenv(
            "LLM_API_KEY",
            getattr(config.llm, "api_key", "") if hasattr(config, "llm") else "",
        )
        llm = LLMManager(provider=provider, base_url=base_url, default_model=model, api_key=api_key)
    except Exception:
        llm = None
        print("LLM not available, proceeding without system purpose generation")

    extractor = C4ArchitectureExtractor(target_repo, llm_manager=llm)
    c4_architecture = extractor.extract()

    api_root = app_path / "Api"
    output_file = api_root / "c4_architecture.json" if (api_root / "c4_architecture.json").exists() else app_path / "c4_architecture.json"
    extractor.save(c4_architecture, output_file)

    print(f"\nContainers: {len(c4_architecture['containers'])}")
    print(f"Components: {len(c4_architecture['components'])}")


if __name__ == "__main__":
    main()
