"""Test script for complete landscape extraction.

Tests all 4 layers of infrastructure landscape analysis.
"""

import json
import logging
from pathlib import Path

from run_complete_landscape import CompleteITLandscapeExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run complete landscape extraction test."""
    # Configuration
    monorepo_path = Path("/Users/iuliarinea/Desktop/Coding/KnowledgeForge/monorepo")
    output_file = Path("complete_landscape.json")
    
    logger.info("=" * 80)
    logger.info("Testing Complete Infrastructure Landscape Extraction")
    logger.info("=" * 80)
    
    # Run extraction
    extractor = CompleteITLandscapeExtractor(monorepo_path)
    landscape = extractor.extract_complete_landscape()
    
    # Save results
    with open(output_file, 'w') as f:
        json.dump(landscape, f, indent=2)
    
    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("EXTRACTION COMPLETE")
    logger.info("=" * 80)
    
    stats = landscape.get('statistics', {})
    logger.info(f"\nLayer 1 - Code:")
    logger.info(f"  Entities: {stats.get('layer1', {}).get('total_entities', 0)}")
    logger.info(f"  Files: {stats.get('layer1', {}).get('total_files', 0)}")
    
    logger.info(f"\nLayer 2 - Application:")
    logger.info(f"  Services: {stats.get('layer2', {}).get('total_services', 0)}")
    logger.info(f"  API Endpoints: {stats.get('layer2', {}).get('total_api_endpoints', 0)}")
    logger.info(f"  External Services: {stats.get('layer2', {}).get('total_external_services', 0)}")
    logger.info(f"  Deployment Dependencies: {stats.get('layer2', {}).get('total_deployment_deps', 0)}")
    
    logger.info(f"\nLayer 3 - Deployment:")
    logger.info(f"  Resources: {stats.get('layer3', {}).get('total_resources', 0)}")
    
    logger.info(f"\nLayer 4 - Data/Workflow:")
    logger.info(f"  Workflows: {stats.get('layer4', {}).get('total_workflows', 0)}")
    
    logger.info(f"\nOutput saved to: {output_file}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
