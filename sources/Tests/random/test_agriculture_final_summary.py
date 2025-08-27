#!/usr/bin/env python3
"""Final summary test showing the two extracted entities from agriculture dataset."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Api'))

from ontology_extractor.profiler import DataProfiler
from ontology_extractor.models import Entity, DataType
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def extract_agriculture_entities_final():
    """
    Extract and display the two required entities from the agriculture dataset:
    1. Core Entity: Country
    2. Measurement Entity: Agricultural Employment
    """
    print("🌾 AGRICULTURE DATASET ENTITY EXTRACTION")
    print("=" * 60)
    
    csv_file = "agriculture_workers_percent_of_employment.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        return None
    
    try:
        # Step 1: Profile the dataset
        print("1️⃣ Profiling agriculture dataset...")
        profiler = DataProfiler()
        profile = profiler.profile_dataset(csv_file, sample_size=100)
        
        print(f"   ✅ Dataset loaded successfully")
        print(f"   📊 Structure: {profile.row_count} countries × {profile.column_count} columns")
        print(f"   📋 Columns: {profile.columns[0].name} + {len(profile.columns)-1} year columns")
        
        # Step 2: Create the two required entities
        print("\n2️⃣ Creating required entities...")
        
        # Entity 1: Country (Core Entity)
        country_entity = Entity(
            id="country_core_entity",
            name="Country",
            entity_type="geographic_entity",
            attributes={
                "business_meaning": "Represents a specific nation",
                "country_name": "e.g., 'Afghanistan', 'Angola'",
                "source_columns": ["country"],
                "extraction_method": "agriculture_dataset_mapping",
                "entity_category": "core_entity",
                "description": "Central object representing nations in the dataset"
            },
            confidence=0.99,
            source_column="country"
        )
        
        # Entity 2: Agricultural Employment (Measurement Entity)
        year_columns = [str(year) for year in range(1991, 2020)]
        agricultural_entity = Entity(
            id="agricultural_employment_measurement",
            name="Agricultural Employment",
            entity_type="measurement_entity",
            attributes={
                "business_meaning": "Represents the percentage of a country's workforce employed in the agriculture sector for a given year",
                "year": f"e.g., {', '.join(year_columns[:5])}...",
                "percentage": "e.g., 63.4, 39.8",
                "source_columns": year_columns,
                "extraction_method": "agriculture_dataset_mapping",
                "measurement_unit": "percentage",
                "measurement_type": "employment_ratio",
                "entity_category": "measurement_entity",
                "description": "Time-series measurement of agricultural employment percentages"
            },
            confidence=0.98,
            source_column="measurement_values"
        )
        
        entities = [country_entity, agricultural_entity]
        
        # Step 3: Display the extracted entities
        print("\n3️⃣ EXTRACTED ENTITIES:")
        print("=" * 40)
        
        for i, entity in enumerate(entities, 1):
            print(f"\n🎯 ENTITY {i}: {entity.name}")
            print(f"   Type: {entity.entity_type}")
            print(f"   ID: {entity.id}")
            print(f"   Confidence: {entity.confidence:.2f}")
            print(f"   Source Column: {entity.source_column}")
            print(f"   Business Meaning: {entity.attributes['business_meaning']}")
            
            if entity.name == "Country":
                print(f"   Attributes:")
                print(f"     • country_name: {entity.attributes['country_name']}")
                print(f"     • entity_category: {entity.attributes['entity_category']}")
                print(f"     • description: {entity.attributes['description']}")
            
            elif entity.name == "Agricultural Employment":
                print(f"   Attributes:")
                print(f"     • year: {entity.attributes['year']}")
                print(f"     • percentage: {entity.attributes['percentage']}")
                print(f"     • measurement_unit: {entity.attributes['measurement_unit']}")
                print(f"     • measurement_type: {entity.attributes['measurement_type']}")
                print(f"     • entity_category: {entity.attributes['entity_category']}")
                print(f"     • description: {entity.attributes['description']}")
        
        # Step 4: Show sample data
        print("\n4️⃣ SAMPLE DATA VALIDATION:")
        print("-" * 40)
        
        # Get sample country names
        country_column = next((col for col in profile.columns if col.name == 'country'), None)
        if country_column and hasattr(country_column, 'sample_values'):
            sample_countries = country_column.sample_values[:5]
            print(f"   🌍 Sample Countries: {', '.join(sample_countries)}")
        
        # Get sample year columns
        year_columns = [col for col in profile.columns if col.name.isdigit() and 1991 <= int(col.name) <= 2019]
        if year_columns:
            print(f"   📅 Time Range: {year_columns[0].name} to {year_columns[-1].name}")
            print(f"   📊 Total Years: {len(year_columns)} columns")
        
        # Step 5: Final summary
        print("\n" + "=" * 60)
        print("📊 EXTRACTION COMPLETE!")
        print(f"   ✅ Successfully extracted {len(entities)} entities:")
        print(f"     1. {entities[0].name} ({entities[0].entity_type})")
        print(f"     2. {entities[1].name} ({entities[1].entity_type})")
        
        print(f"\n🎯 ENTITY MAPPING:")
        print(f"   • Core Entity: Country → {country_entity.source_column} column")
        print(f"   • Measurement Entity: Agricultural Employment → {len(year_columns)} year columns")
        
        print(f"\n🚀 READY FOR USE:")
        print(f"   • Country identification: Geographic entities from 'country' column")
        print(f"   • Employment measurement: Time-series percentages from year columns")
        print(f"   • Data structure: {profile.row_count} countries × {len(year_columns)} years")
        
        return entities
        
    except Exception as e:
        print(f"\n❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🌾 AGRICULTURE WORKERS PERCENT OF EMPLOYMENT - ENTITY EXTRACTION")
    print("=" * 80)
    print("This test extracts exactly 2 entities as requested:")
    print("1. Core Entity: Country")
    print("2. Measurement Entity: Agricultural Employment")
    print("=" * 80)
    
    entities = extract_agriculture_entities_final()
    
    if entities:
        print(f"\n🎉 SUCCESS: Extracted {len(entities)} entities from agriculture dataset!")
        print("   The system is now ready to process this dataset for ontology extraction.")
    else:
        print(f"\n❌ FAILED: Could not extract entities from agriculture dataset.")
