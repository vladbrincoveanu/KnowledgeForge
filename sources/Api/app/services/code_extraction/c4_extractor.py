"""C4 Model-based architecture extractor.

Implements the C4 Model approach to avoid information overload:
- Level 1 (Context): System + External dependencies
- Level 2 (Container): Deployable units (services, databases, frontends)
- Level 3 (Component): Public entry points only (not internal details)

Focus on architectural boundaries, not code details.
"""

import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.services.c4.containers import ContainerManager
from app.services.c4.context import ContextManager
from app.services.c4.components.component_extractor import ComponentExtractor
from app.services.c4.components.models import ComponentObject
from app.services.c4.graph_writer import GraphWriter
from app.infrastructure.graph.neo4j_client import Neo4jClient
from app.domain.exceptions import GraphDatabaseError
from app.services.code_extraction.llm_enrichment import enrich_with_llm_descriptions
from app.services.code_extraction.component_extractor import link_components_to_containers

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
        self.llm_manager = llm_manager

        # C4 Model data structures
        self.system_context = {}   # Level 1
        self.containers = {}       # Level 2
        self.components = {}       # Level 3
        self.context_relationships = []
        self.container_relationships = []
        self.cluster_metadata = {}

        # Extractors
        self.container_manager = ContainerManager(self.repo_path, llm_manager)
        self.component_extractor = ComponentExtractor()

    def extract(self, max_components_per_domain: int = 10, group_components_by_domain: bool = False, task_id: Optional[str] = None, repo_url: Optional[str] = None) -> dict[str, Any]:
        """Extract C4 architecture."""
        tracker = PerformanceTracker(
            task_id=task_id or f"extract_{int(time.time())}",
            repository_url=repo_url or str(self.repo_path)
        )

        logger.info("Starting C4 Model extraction...")
        logger.info("=" * 80)

        # Level 2: Containers first (needed for domain detection)
        logger.info("\n📦 LEVEL 2: Containers")
        logger.info("-" * 80)
        t0 = time.time()
        self._extract_level2_containers()
        containers_ms = (time.time() - t0) * 1000
        logger.info(f"✓ Containers: {len(self.containers)} [{containers_ms:.0f}ms]")
        if tracker:
            tracker.results.add_phase("L2_Containers", containers_ms)

        # Level 1: Context (System + External Dependencies + IT Landscape metadata)
        logger.info("\n📊 LEVEL 1: System Context")
        logger.info("-" * 80)
        t0 = time.time()
        self._extract_level1_context()
        context_ms = (time.time() - t0) * 1000
        logger.info(f"✓ System: {self.system_context.get('name', 'Unknown')}")
        logger.info(f"✓ Owner: {self.system_context.get('owner_team', self.system_context.get('owner', 'Unknown'))}")
        logger.info(f"✓ Domain: {self.system_context.get('business_domain', self.system_context.get('domain', 'Unknown'))}")
        logger.info(f"✓ External dependencies: {len(self.system_context.get('external_dependencies', []))}")
        logger.info(f"  [Level 1 completed in {context_ms:.0f}ms]")
        if tracker:
            tracker.results.add_phase("L1_Context", context_ms)

        # Build container relationships
        t0 = time.time()
        self.container_relationships = self.container_manager.build_container_relationships()
        self.cluster_metadata = self.container_manager.detect_cluster_metadata()
        rels_ms = (time.time() - t0) * 1000
        if tracker:
            tracker.results.add_phase("Container_Relationships", rels_ms)

        # Level 3: Components
        logger.info("\n🔌 LEVEL 3: Components")
        logger.info("-" * 80)
        t0 = time.time()
        self._extract_level3_components()
        components_ms = (time.time() - t0) * 1000
        logger.info(f"✓ Components: {len(self.components)} [{components_ms:.0f}ms]")
        if tracker:
            tracker.results.add_phase("L3_Components", components_ms)

        link_components_to_containers(self.components, self.containers)
        logger.info("✓ Component-container links created")

        # Group by domain if too many
        if group_components_by_domain and len(self.components) > max_components_per_domain:
            logger.info(f"✓ Grouping {len(self.components)} components by domain...")
            self._group_by_domain()

        # Enrich with LLM-generated descriptions
        t0 = time.time()
        enrich_with_llm_descriptions(
            self.system_context, self.containers, self.components,
            self.context_relationships, self.container_relationships,
            self.llm_manager,
        )
        llm_ms = (time.time() - t0) * 1000
        logger.info(f"✓ LLM enrichment completed [{llm_ms:.0f}ms]")
        if tracker:
            tracker.results.add_phase("LLM_Enrichment", llm_ms)

        if tracker:
            tracker.save()
            logger.info(f"\n📊 Benchmark saved: {tracker.results.task_id}_benchmark.json")

        # Build final structure
        c4_architecture = {
            "c4_model_version": "1.0",
            "system_context": self.system_context,
            "containers": list(self.containers.values()),
            "components": list(self.components.values()),
            "relationships": {
                "context": self.context_relationships,
                "containers": self.container_relationships,
            },
            "metadata": {
                "total_containers": len(self.containers),
                "total_components": len(self.components),
                "extraction_approach": "c4_model",
                "runtime": {
                    "platform": "Kubernetes" if self.cluster_metadata else "Unknown",
                    "cluster": self.cluster_metadata,
                },
            }
        }

        logger.info("\n" + "=" * 80)
        logger.info("✅ C4 Model Extraction Complete")
        logger.info("=" * 80)
        logger.info(f"Level 1 (Context): 1 system, {len(self.system_context.get('external_dependencies', []))} external deps")
        logger.info(f"Level 2 (Containers): {len(self.containers)} deployable units")
        logger.info(f"Level 3 (Components): {len(self.components)} public entry points")

        # Write to Neo4j (extraction fails if Neo4j unavailable)
        try:
            graph_writer = GraphWriter(Neo4jClient.from_config())
            graph_writer.write(task_id, c4_architecture)
        except GraphDatabaseError as e:
            logger.error(f"Neo4j write failed for extraction {task_id}: {e}")
            raise

        return c4_architecture

    def _extract_level1_context(self):
        """Extract Level 1: System Context using ContextManager."""
        context_manager = ContextManager(
            self.repo_path, self.llm_manager, self.containers,
        )
        self.system_context = context_manager.extract_context()
        self.context_relationships = context_manager.build_context_relationships(
            self.system_context
        )

    def _extract_level2_containers(self):
        """Extract Level 2: Containers (Deployable Units)."""
        self.containers = self.container_manager.detect_all_containers()
        # Second pass: LLM enrichment (no-op when llm_manager is None)
        self.container_manager.enrich_containers_with_llm()

    # Container types that are infrastructure — no components expected
    _INFRA_CONTAINER_TYPES = frozenset({
        "Database", "Cache", "Message Broker",
        "Helm Deployed Service",
    })

    def _extract_level3_components(self) -> None:
        """Extract Level 3: Components using ComponentExtractor (tree-sitter + graph + grouping)."""
        for container_name, container in self.containers.items():
            # Skip infra containers that have no application code
            ctype = container.get("container_type", "")
            if ctype in self._INFRA_CONTAINER_TYPES:
                continue

            container_rel_path = container.get("path", "")
            container_abs_path = str(self.repo_path / container_rel_path) if container_rel_path else str(self.repo_path)

            try:
                component_objects = self.component_extractor.extract(container_abs_path)
            except Exception as exc:
                logger.warning("ComponentExtractor failed for container '%s': %s", container_name, exc)
                component_objects = []

            # Fallback: if no components were extracted but the container has
            # source files, create a single entry-point component so the
            # container isn't invisible at Level 3.
            if not component_objects:
                fallback = self._create_fallback_component(
                    container_name, container_rel_path, container_abs_path, container,
                )
                if fallback:
                    component_objects = [fallback]

            for obj in component_objects:
                comp_dict = self._component_object_to_dict(obj, container_name, container_rel_path)
                # Namespace component IDs by container to avoid cross-container collisions
                unique_id = f"{container_name}::{obj.component_id}"
                self.components[unique_id] = comp_dict

    def _create_fallback_component(
        self, container_name: str, container_rel_path: str,
        container_abs_path: str, container: dict,
    ) -> "ComponentObject | None":
        """Create a single fallback component from the entry-point file."""
        from app.services.c4.components.models import (
            ComponentObject, ComponentType, ExtractionMethod,
        )
        # Look for common entry-point files
        entry_candidates = [
            "main.py", "app.py", "server.py", "index.js", "index.ts",
            "main.go", "Main.java", "Program.cs", "Startup.cs",
            "src/index.js", "src/index.ts", "src/main.ts", "src/app.ts",
            "src/server.ts", "src/server.js", "cmd/main.go",
        ]
        entry_file = None
        for candidate in entry_candidates:
            full = Path(container_abs_path) / candidate
            if full.exists():
                entry_file = candidate
                break

        if not entry_file:
            return None

        # Derive a readable name from the container name
        # e.g. "omnipay-disputes" → "Disputes"
        parts = container_name.split("-")
        # Use last meaningful segment
        name = parts[-1].capitalize() if len(parts) > 1 else parts[0].capitalize()

        return ComponentObject(
            component_id=f"fallback_{container_name}",
            name=f"{name}API",
            technology=container.get("technology", "Unknown"),
            component_type=ComponentType.CONTROLLER,
            extraction_method=ExtractionMethod.COMMUNITY_DETECTION,
            confidence=0.3,
            code_elements=[],
            metadata={"fallback": True, "entry_file": entry_file},
        )

    def _component_object_to_dict(self, obj: ComponentObject, container_name: str, container_rel_path: str) -> dict:
        """Convert a ComponentObject to the dict format used in the C4 output."""
        file_path = obj.code_elements[0].file_path if obj.code_elements else None
        if file_path and container_rel_path:
            try:
                file_path = str(Path(container_rel_path) / Path(file_path).name)
            except Exception:
                pass

        technology = obj.technology or (obj.code_elements[0].language if obj.code_elements else None)

        return {
            "c4_level": 3,
            "type": "component",
            "name": obj.name,
            "component_type": obj.component_type.value if obj.component_type else "Component",
            "container": container_name,
            "file": file_path,
            "documentation": obj.description or None,
            "technology": technology,
            "confidence": obj.confidence,
            "extraction_method": obj.extraction_method.value,
            "tags": obj.tags,
            "metadata": obj.metadata,
        }

    def _group_by_domain(self):
        """Group components by domain if too many."""
        domains = defaultdict(list)

        for comp_id, comp in self.components.items():
            file_path = comp.get('file', '')
            parts = Path(file_path).parts
            if len(parts) > 0:
                domain = parts[0]
                domains[domain].append(comp)

        grouped_components = {}
        for domain, comps in domains.items():
            if len(comps) > 3:
                grouped_components[domain] = {
                    "c4_level": 3,
                    "type": "component_group",
                    "name": domain,
                    "component_type": "Domain",
                    "component_count": len(comps),
                    "components": [c['name'] for c in comps],
                }
            else:
                for comp in comps:
                    grouped_components[f"{domain}::{comp['name']}"] = comp

        self.components = grouped_components

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
        provider = os.getenv("LLM_PROVIDER", "lmstudio")
        base_url = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
        model = os.getenv("LLM_MODEL", "qwen/qwen2.5-vl-7b")
        api_key = os.getenv("LLM_API_KEY", "")
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
