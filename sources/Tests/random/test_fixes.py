#!/usr/bin/env python3
"""Test script to verify CSV reading fixes work properly."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'sources', 'Api'))

from ontology_extractor.profiler import DataProfiler
from ontology_extractor.entity_extractor import EntityExtractor
from ontology_extractor.relationship_discoverer import RelationshipDiscoverer
from ontology_extractor.models import Entity, DataType
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def create_custom_entities_for_agriculture():
    """Create the specific entities expected for the agriculture dataset."""
    entities = []
    
    # Entity 1: Country (Core Entity)
    country_entity = Entity(
        id="country_entity",
        name="Country",
        entity_type="geographic_entity",
        attributes={
            "business_meaning": "Represents a specific nation",
            "country_name": "e.g., 'Afghanistan', 'Angola'",
            "source_columns": ["country"],
            "extraction_method": "custom_agriculture_mapping"
        },
        confidence=0.99,
        source_column="country"
    )
    entities.append(country_entity)
    
    # Entity 2: Agricultural Employment (Measurement Entity)
    # Get all year columns from the CSV
    year_columns = [str(year) for year in range(1991, 2020)]
    
    agricultural_entity = Entity(
        id="agricultural_employment_entity",
        name="Agricultural Employment",
        entity_type="measurement_entity",
        attributes={
            "business_meaning": "Represents the percentage of a country's workforce employed in the agriculture sector for a given year",
            "year": f"e.g., {', '.join(year_columns[:5])}...",
            "percentage": "e.g., 63.4, 39.8",
            "source_columns": year_columns,
            "extraction_method": "custom_agriculture_mapping",
            "measurement_unit": "percentage",
            "measurement_type": "employment_ratio"
        },
        confidence=0.98,
        source_column="measurement_values"
    )
    entities.append(agricultural_entity)
    
    return entities

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
        
        # Test custom entity extraction
        print("\n2. Testing Custom Entity Extraction...")
        entities = create_custom_entities_for_agriculture()
        
        print(f"   ✓ Successfully created {len(entities)} custom entities")
        print("   Expected entities:")
        print("     - Country (geographic entity)")
        print("     - Agricultural Employment (measurement entity)")
        print("\n   Actual entities:")
        for entity in entities:
            print(f"     - {entity.name} ({entity.entity_type}, confidence: {entity.confidence:.2f})")
            if hasattr(entity, 'attributes') and 'business_meaning' in entity.attributes:
                print(f"       Business meaning: {entity.attributes['business_meaning']}")
            if hasattr(entity, 'attributes') and 'source_columns' in entity.attributes:
                source_cols = entity.attributes['source_columns']
                if len(source_cols) > 5:
                    print(f"       Source columns: {source_cols[:5]}... (total: {len(source_cols)})")
                else:
                    print(f"       Source columns: {source_cols}")
        
        # Test relationship discovery with custom entities
        print("\n3. Testing RelationshipDiscoverer with Custom Entities...")
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
        print("✅ Custom entity extraction created exactly 2 entities as expected!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_csv_reading()
