"""C4 Model-based architecture extractor.

Implements the C4 Model approach to avoid information overload:
- Level 1 (Context): System + External dependencies
- Level 2 (Container): Deployable units (services, databases, frontends)
- Level 3 (Component): Public entry points only (not internal details)

Focus on architectural boundaries, not code details.
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.c4.containers import ContainerManager
from app.services.c4.context import ContextManager
from app.services.code_extraction.language_detectors import (
    PythonLanguageDetector,
    JavaScriptLanguageDetector,
    JavaLanguageDetector,
    DotNetLanguageDetector,
)
from app.services.code_extraction.llm_enrichment import enrich_with_llm_descriptions
from app.services.code_extraction.component_extractor import (
    extract_level3_components,
    link_components_to_containers,
)

logger = logging.getLogger(__name__)


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

        # Language detectors (Strategy Pattern)
        self.language_detectors = [
            PythonLanguageDetector(),
            JavaScriptLanguageDetector(),
            JavaLanguageDetector(),
            DotNetLanguageDetector(),
        ]

    def extract(self, max_components_per_domain: int = 10, group_components_by_domain: bool = False) -> dict[str, Any]:
        """Extract C4 architecture."""
        logger.info("Starting C4 Model extraction...")
        logger.info("=" * 80)

        # Level 2: Containers first (needed for domain detection)
        logger.info("\n📦 LEVEL 2: Containers")
        logger.info("-" * 80)
        self._extract_level2_containers()
        logger.info(f"✓ Containers: {len(self.containers)}")

        # Level 1: Context (System + External Dependencies + IT Landscape metadata)
        logger.info("\n📊 LEVEL 1: System Context")
        logger.info("-" * 80)
        self._extract_level1_context()
        logger.info(f"✓ System: {self.system_context.get('name', 'Unknown')}")
        logger.info(f"✓ Owner: {self.system_context.get('owner_team', self.system_context.get('owner', 'Unknown'))}")
        logger.info(f"✓ Domain: {self.system_context.get('business_domain', self.system_context.get('domain', 'Unknown'))}")
        logger.info(f"✓ External dependencies: {len(self.system_context.get('external_dependencies', []))}")

        # Build container relationships
        self.container_relationships = self.container_manager.build_container_relationships()
        self.cluster_metadata = self.container_manager.detect_cluster_metadata()

        # Level 3: Components
        logger.info("\n🔌 LEVEL 3: Components")
        logger.info("-" * 80)
        extract_level3_components(
            self.repo_path, self.containers, self.components,
            [], self.language_detectors, self.llm_manager,
        )
        logger.info(f"✓ Components: {len(self.components)}")

        link_components_to_containers(self.components, self.containers)
        logger.info("✓ Component-container links created")

        # Group by domain if too many
        if group_components_by_domain and len(self.components) > max_components_per_domain:
            logger.info(f"✓ Grouping {len(self.components)} components by domain...")
            self._group_by_domain()

        # Enrich with LLM-generated descriptions
        enrich_with_llm_descriptions(
            self.system_context, self.containers, self.components,
            self.context_relationships, self.container_relationships,
            self.llm_manager,
        )

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

    def find_repo_root(start: Path) -> Path:
        for parent in [start] + list(start.parents):
            if (parent / ".git").exists():
                return parent
        return start

    app_path = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(app_path))

    from infrastructure.llm.llm_manager import LLMManager

    repo_root = find_repo_root(app_path)
    monorepo_path = repo_root / "monorepo"
    target_repo = monorepo_path if monorepo_path.exists() else repo_root

    try:
        import os
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        model = os.getenv("LMSTUDIO_MODEL_NAME", "qwen/qwen2.5-vl-7b")
        llm = LLMManager(lmstudio_url=base_url, default_model=model)
    except Exception:
        llm = None
        print("LLM not available, proceeding without system purpose generation")

    extractor = C4ArchitectureExtractor(target_repo, llm_manager=llm)
    c4_architecture = extractor.extract()

    api_root = repo_root / "sources" / "Api"
    output_file = api_root / "c4_architecture.json" if api_root.exists() else repo_root / "c4_architecture.json"
    extractor.save(c4_architecture, output_file)

    print(f"\nContainers: {len(c4_architecture['containers'])}")
    print(f"Components: {len(c4_architecture['components'])}")


if __name__ == "__main__":
    main()
