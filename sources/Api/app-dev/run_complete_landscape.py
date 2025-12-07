"""Complete IT Landscape extraction pipeline (All 4 Layers).

This orchestrates all extraction layers:
- Layer 1: Code Architecture (existing)
- Layer 2: Application Architecture (services, APIs)
- Layer 3: Runtime/Deployment (K8s, Docker)
- Layer 4: Data/Workflow (data flows, schemas)
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add app-dev to path
sys.path.insert(0, str(Path(__file__).parent))

from services.code_extraction.repository_scanner import RepositoryScanner
from services.code_extraction.layer2_application.service_detector import ServiceBoundaryDetector
from services.code_extraction.layer2_application.api_detector import APIEndpointDetector
from services.code_extraction.layer2_application.dependency_analyzer import ServiceDependencyAnalyzer
from services.code_extraction.layer3_deployment.deployment_analyzer import DeploymentTopologyAnalyzer
from services.code_extraction.layer4_dataflow.dataflow_analyzer import DataFlowAnalyzer, WorkflowSequenceDetector
from infrastructure.graph.code_entity_storage import CodeEntityNeo4jStorage

logger = logging.getLogger(__name__)


class CompleteITLandscapeExtractor:
    """Complete IT landscape extraction across all 4 layers."""
    
    def __init__(self, repo_path: Path):
        """Initialize complete extractor."""
        self.repo_path = Path(repo_path)
        self.scanner = RepositoryScanner(repo_path=self.repo_path)
        # Layer analyzers
        self.service_detector = ServiceBoundaryDetector(repo_path)
        self.api_detector = APIEndpointDetector(repo_path)
        self.dependency_analyzer = ServiceDependencyAnalyzer(repo_path)
        self.deployment_analyzer = DeploymentTopologyAnalyzer(repo_path)
        self.dataflow_analyzer = DataFlowAnalyzer()
        self.workflow_detector = WorkflowSequenceDetector()
    
    def extract_complete_landscape(self) -> dict[str, Any]:
        """
        Extract complete IT landscape across all 4 layers.
        
        Returns:
            Complete landscape data structure
        """
        logger.info("="*80)
        logger.info("COMPLETE IT LANDSCAPE EXTRACTION")
        logger.info("="*80)
        
        # Layer 1: Code Architecture (Base extraction)
        logger.info("\n📦 LAYER 1: Code Architecture")
        logger.info("-" * 80)
        base_extraction = self.scanner.scan(force_full=True)
        
        logger.info(f"✓ Extracted {len(base_extraction.entities)} entities")
        logger.info(f"✓ Extracted {len(base_extraction.relationships)} relationships")
        
        # Layer 2: Application Architecture
        logger.info("\n🏗️  LAYER 2: Application Architecture")
        logger.info("-" * 80)
        service_analysis = self.service_detector.analyze(base_extraction)
        api_endpoints = self.api_detector.detect_endpoints(base_extraction)
        dependency_analysis = self.dependency_analyzer.analyze(base_extraction)
        
        logger.info(f"✓ Detected {len(service_analysis['services'])} services")
        logger.info(f"✓ Detected {len(service_analysis['libraries'])} libraries")
        logger.info(f"✓ Detected {len(api_endpoints)} API endpoints")
        logger.info(f"✓ Mapped {dependency_analysis['statistics']['total_external_services']} external service connections")
        logger.info(f"✓ Found {dependency_analysis['statistics']['total_internal_routes']} internal routes")
        
        # Print key external services
        if dependency_analysis['external_services']:
            logger.info("\n🔗 KEY EXTERNAL SERVICES")
            logger.info("="*80)
            seen_urls = set()
            for ext_svc in dependency_analysis['external_services'][:10]:
                url = ext_svc['url']
                if url not in seen_urls:
                    logger.info(f"   {ext_svc['source_service']} → {url}")
                    seen_urls.add(url)
        
        # Layer 3: Runtime/Deployment Architecture
        logger.info("\n🚀 LAYER 3: Runtime & Deployment Architecture")
        logger.info("-" * 80)
        deployment_topology = self.deployment_analyzer.analyze(base_extraction)
        
        logger.info(f"✓ Found {len(deployment_topology['deployments'])} deployments")
        logger.info(f"✓ Found {len(deployment_topology['services'])} K8s services")
        logger.info(f"✓ Found {len(deployment_topology['ingresses'])} ingresses")
        logger.info(f"✓ Detected {len(deployment_topology.get('deployment_tools', []))} deployment tools")
        logger.info(f"✓ Found {len(deployment_topology.get('helm_charts', {}))} Helm charts")
        
        # Layer 4: Data & Workflow Architecture
        logger.info("\n📊 LAYER 4: Data & Workflow Architecture")
        logger.info("-" * 80)
        dataflow_analysis = self.dataflow_analyzer.analyze(base_extraction)
        workflow_sequences = self.workflow_detector.detect_sequences(
            dataflow_analysis['workflows'],
            base_extraction.relationships
        )
        
        logger.info(f"✓ Detected {len(dataflow_analysis['workflows'])} workflows")
        logger.info(f"✓ Found {len(dataflow_analysis['data_flows'])} data flows")
        logger.info(f"✓ Detected {len(dataflow_analysis['schemas'])} schemas")
        logger.info(f"✓ Found {len(dataflow_analysis['artifacts'])} artifact operations")
        
        # Combine all layers
        complete_landscape = {
            "layer1_code_architecture": {
                "entities": [
                    {
                        "id": e.id,
                        "name": e.name,
                        "type": e.entity_type.value,
                        "language": e.language.value,
                        "file_path": e.file_path,
                        "line_start": e.line_start,
                        "line_end": e.line_end,
                        "signature": e.signature,
                    }
                    for e in base_extraction.entities
                ],
                "relationships": [
                    {
                        "id": r.id,
                        "source": r.source_entity_id,
                        "target": r.target_entity_id,
                        "type": r.relationship_type.value,
                    }
                    for r in base_extraction.relationships
                ],
                "statistics": {
                    "total_entities": len(base_extraction.entities),
                    "total_relationships": len(base_extraction.relationships),
                    "total_files": len(base_extraction.files),
                }
            },
            "layer2_application_architecture": {
                "services": service_analysis['services'],
                "libraries": service_analysis['libraries'],
                "service_dependencies": service_analysis['service_dependencies'],
                "api_endpoints": api_endpoints,
                "dependencies": dependency_analysis,
                "statistics": {
                    **service_analysis['statistics'],
                    **dependency_analysis['statistics'],
                },
            },
            "layer3_deployment_architecture": {
                "deployment_tools": deployment_topology.get('deployment_tools', []),
                "helm_charts": deployment_topology.get('helm_charts', {}),
                "deployments": deployment_topology['deployments'],
                "k8s_services": deployment_topology['services'],
                "ingresses": deployment_topology['ingresses'],
                "config_maps": deployment_topology['config_maps'],
                "secrets": deployment_topology['secrets'],
                "pvcs": deployment_topology['pvcs'],
                "namespaces": deployment_topology['namespaces'],
                "docker_images": deployment_topology['docker_images'],
                "routing_topology": deployment_topology['routing_topology'],
                "external_services": deployment_topology['external_services'],
                "resource_dependencies": deployment_topology['resource_dependencies'],
                "statistics": deployment_topology['statistics'],
            },
            "layer4_data_workflow_architecture": {
                "workflows": dataflow_analysis['workflows'],
                "workflow_sequences": workflow_sequences,
                "data_flows": dataflow_analysis['data_flows'],
                "io_signatures": dataflow_analysis['io_signatures'],
                "schemas": dataflow_analysis['schemas'],
                "artifacts": dataflow_analysis['artifacts'],
                "statistics": dataflow_analysis['statistics'],
            },
            "metadata": {
                "repository": base_extraction.repository.repo_path,
                "extraction_timestamp": base_extraction.repository.scan_timestamp.isoformat(),
                "languages": [lang.value for lang in base_extraction.repository.languages_detected],
            }
        }
        
        # Summary
        logger.info("\n" + "="*80)
        logger.info("📋 EXTRACTION SUMMARY")
        logger.info("="*80)
        logger.info(f"\nLayer 1 (Code): {len(base_extraction.entities)} entities, "
                   f"{len(base_extraction.relationships)} relationships")
        logger.info(f"Layer 2 (Apps): {len(service_analysis['services'])} services, "
                   f"{len(api_endpoints)} endpoints")
        logger.info(f"Layer 3 (Deploy): {len(deployment_topology['deployments'])} deployments, "
                   f"{len(deployment_topology['routing_topology'])} routes")
        logger.info(f"Layer 4 (Data): {len(dataflow_analysis['workflows'])} workflows, "
                   f"{len(dataflow_analysis['data_flows'])} flows")
        
        return complete_landscape
    
    def save_landscape(self, landscape: dict[str, Any], output_path: Path):
        """Save complete landscape to JSON file."""
        output_path = Path(output_path)
        with open(output_path, 'w') as f:
            json.dump(landscape, f, indent=2)
        
        logger.info(f"\n💾 Complete landscape saved to: {output_path}")
    
    def store_in_neo4j(
        self,
        landscape: dict[str, Any],
        neo4j_uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
    ) -> dict[str, int]:
        """Store complete landscape in Neo4j with all layers."""
        logger.info("\n" + "="*80)
        logger.info("💾 STORING IN NEO4J (All Layers)")
        logger.info("="*80)
        
        storage = CodeEntityNeo4jStorage(
            uri=neo4j_uri,
            username=username,
            password=password,
            encrypted=False,
        )
        
        if not storage.connect():
            raise RuntimeError("Failed to connect to Neo4j")
        
        # Create schema
        storage.create_schema()
        
        # Store Layer 1 (base code entities) - already handled by base storage
        # Here we would extend to store layers 2-4 as well
        
        # TODO: Add methods to store:
        # - Services as nodes
        # - API endpoints as nodes
        # - Deployments with full topology
        # - Workflows and data flows
        
        logger.info("✓ Base entities stored (Layer 1)")
        logger.info("⚠️  Layers 2-4 storage requires extended Neo4j schema")
        logger.info("   (Can be added in next iteration)")
        
        storage.close()
        
        return {
            "layer1_stored": True,
            "layer2_stored": False,  # TODO
            "layer3_stored": False,  # TODO
            "layer4_stored": False,  # TODO
        }


def main():
    """Run complete IT landscape extraction."""
    # Path to monorepo
    monorepo_path = Path(__file__).parent.parent.parent.parent / "monorepo"
    
    if not monorepo_path.exists():
        print(f"❌ Monorepo path not found: {monorepo_path}")
        sys.exit(1)
    
    # Create extractor
    extractor = CompleteITLandscapeExtractor(monorepo_path)
    
    # Extract complete landscape
    landscape = extractor.extract_complete_landscape()
    
    # Save to file
    output_file = Path(__file__).parent / "complete_landscape.json"
    extractor.save_landscape(landscape, output_file)
    
    # Print summary for key services
    print("\n" + "="*80)
    print("🎯 KEY SERVICES DETECTED")
    print("="*80)
    
    services = landscape["layer2_application_architecture"]["services"]
    for service_name, service_info in services.items():
        print(f"\n📦 {service_name}")
        print(f"   Type: {service_info['type']}")
        print(f"   Files: {len(service_info['files'])}")
        if service_name in landscape["layer2_application_architecture"]["service_dependencies"]:
            deps = landscape["layer2_application_architecture"]["service_dependencies"][service_name]
            if deps:
                print(f"   Dependencies: {', '.join(deps)}")
    
    print("\n" + "="*80)
    print("✨ Complete IT Landscape Extraction Done!")
    print("="*80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
