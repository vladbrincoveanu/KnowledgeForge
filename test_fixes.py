#!/usr/bin/env python3
"""Test script to verify CSV reading fixes work properly."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'sources', 'Api'))

from ontology_extractor.profiler import DataProfiler
from ontology_extractor.entity_extractor import EntityExtractor
from ontology_extractor.relationship_discoverer import RelationshipDiscoverer
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_csv_reading():
    """Test CSV reading with the agriculture dataset."""
    csv_file = "agriculture_workers_percent_of_employment.csv"
    
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found in current directory")
        return
    
    print(f"Testing CSV reading with {csv_file}")
    print("=" * 50)
    
    try:
        # Test the profiler
        print("1. Testing DataProfiler...")
        profiler = DataProfiler()
        profile = profiler.profile_dataset(csv_file, sample_size=100)
        
        print(f"   ✓ Successfully profiled dataset")
        print(f"   ✓ Columns: {[col.name for col in profile.columns]}")
        print(f"   ✓ Rows: {profile.row_count}")
        print(f"   ✓ Column count: {profile.column_count}")
        
        # Check for auto-generated column names
        auto_generated = [col for col in profile.columns if col.name.startswith('column')]
        if auto_generated:
            print(f"   ⚠️  Warning: Found auto-generated column names: {[col.name for col in auto_generated]}")
        else:
            print("   ✓ No auto-generated column names detected")
        
        # Test entity extraction
        print("\n2. Testing EntityExtractor...")
        entity_extractor = EntityExtractor()
        
        # Create config for entity extraction
        entity_config = {
            'llm_enabled': False,  # Disable LLM to avoid setup issues
            'confidence_threshold': 0.5,
            'max_entities': 50,
            'use_regex': True,
            'use_pattern_analysis': True,
            'use_llm_inference': False
        }
        
        entities = entity_extractor.extract_entities(csv_file, profile.columns, entity_config)
        
        print(f"   ✓ Successfully extracted {len(entities)} entities")
        print("   Expected entities:")
        print("     - Country (geographic entity)")
        print("     - Agricultural Employment (measurement entity)")
        print("     - Year (temporal entity)")
        print("\n   Actual entities:")
        for entity in entities:
            print(f"     - {entity.name} ({entity.entity_type}, confidence: {entity.confidence:.2f})")
            if hasattr(entity, 'attributes') and 'business_meaning' in entity.attributes:
                print(f"       Business meaning: {entity.attributes['business_meaning']}")
        
        # Test relationship discovery
        print("\n3. Testing RelationshipDiscoverer...")
        relationship_discoverer = RelationshipDiscoverer()
        
        config = {
            'fk_overlap_threshold': 0.8,
            'relationship_threshold': 0.6,
            'max_relationships': 100
        }
        
        relationships = relationship_discoverer.discover_relationships(
            csv_file, entities, profile.columns, config
        )
        
        print(f"   ✓ Successfully discovered {len(relationships)} relationships")
        for rel in relationships[:5]:  # Show first 5 relationships
            print(f"     - {rel.relationship_type} (confidence: {rel.confidence:.2f})")
        
        print("\n" + "=" * 50)
        print("✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_csv_reading()
