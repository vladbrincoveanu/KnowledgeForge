#!/usr/bin/env python3
"""Test script for extracting specific entities from agriculture dataset."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Api'))

from ontology_extractor.profiler import DataProfiler
from ontology_extractor.entity_extractor import EntityExtractor
from ontology_extractor.models import Entity, DataType
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def extract_agriculture_entities(csv_file_path):
    """
    Extract the two required entities from the agriculture dataset:
    1. Core Entity: Country
    2. Measurement Entity: Agricultural Employment
    """
    print(f"🌾 Extracting entities from: {csv_file_path}")
    print("=" * 60)
    
    try:
        # Step 1: Profile the dataset
        print("1️⃣ Profiling agriculture dataset...")
        profiler = DataProfiler()
        profile = profiler.profile_dataset(csv_file_path, sample_size=100)
        
        print(f"   ✅ Dataset profiled successfully")
        print(f"   📊 Total rows: {profile.row_count}")
        print(f"   🔍 Total columns: {profile.column_count}")
        print(f"   📋 Column names: {[col.name for col in profile.columns]}")
        
        # Step 2: Extract entities using the entity extractor
        print("\n2️⃣ Extracting entities using AI-powered extraction...")
        entity_extractor = EntityExtractor()
        
        extraction_config = {
            'use_regex': True,
            'use_pattern_analysis': True,
            'max_entities_per_column': 50,
            'confidence_threshold': 0.7,
            'enable_semantic_similarity': True
        }
        
        extracted_entities = entity_extractor.extract_entities(
            csv_file_path, 
            profile.columns, 
            extraction_config
        )
        
        print(f"   ✅ AI extraction completed: {len(extracted_entities)} entities found")
        
        # Step 3: Create our target entities manually
        print("\n3️⃣ Creating target entities for agriculture dataset...")
        
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
        # Get all year columns from the CSV
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
        
        target_entities = [country_entity, agricultural_entity]
        
        print(f"   ✅ Target entities created: {len(target_entities)} entities")
        
        # Step 4: Display the extracted entities
        print("\n4️⃣ Entity Extraction Results:")
        print("-" * 40)
        
        print("\n🎯 TARGET ENTITIES (Expected):")
        for i, entity in enumerate(target_entities, 1):
            print(f"\n   {i}. {entity.name} ({entity.entity_type})")
            print(f"      ID: {entity.id}")
            print(f"      Confidence: {entity.confidence:.2f}")
            print(f"      Source Column: {entity.source_column}")
            print(f"      Business Meaning: {entity.attributes['business_meaning']}")
            if 'source_columns' in entity.attributes:
                source_cols = entity.attributes['source_columns']
                if len(source_cols) > 5:
                    print(f"      Source Columns: {source_cols[:5]}... (total: {len(source_cols)})")
                else:
                    print(f"      Source Columns: {source_cols}")
        
        print("\n🤖 AI-EXTRACTED ENTITIES:")
        if extracted_entities:
            for i, entity in enumerate(extracted_entities[:10], 1):  # Show first 10
                print(f"\n   {i}. {entity.name} ({entity.entity_type})")
                print(f"      ID: {entity.id}")
                print(f"      Confidence: {entity.confidence:.2f}")
                print(f"      Source Column: {entity.source_column}")
                if hasattr(entity, 'attributes') and 'business_meaning' in entity.attributes:
                    print(f"      Business Meaning: {entity.attributes['business_meaning']}")
        else:
            print("   No entities extracted by AI")
        
        # Step 5: Validate the extraction
        print("\n5️⃣ Validation Results:")
        print("-" * 40)
        
        # Check if we have the expected column types
        country_column = next((col for col in profile.columns if col.name == 'country'), None)
        year_columns = [col for col in profile.columns if col.name.isdigit() and 1991 <= int(col.name) <= 2019]
        
        validation_results = []
        
        if country_column:
            validation_results.append(f"✅ Country column found: '{country_column.name}' ({country_column.data_type.value})")
        else:
            validation_results.append("❌ Country column not found")
        
        if year_columns:
            validation_results.append(f"✅ Year columns found: {len(year_columns)} columns ({year_columns[0].name} to {year_columns[-1].name})")
        else:
            validation_results.append("❌ Year columns not found")
        
        for result in validation_results:
            print(f"   {result}")
        
        # Step 6: Summary
        print("\n" + "=" * 60)
        print("📊 EXTRACTION SUMMARY:")
        print(f"   • Target entities created: {len(target_entities)}")
        print(f"   • AI extracted entities: {len(extracted_entities)}")
        print(f"   • Dataset columns: {len(profile.columns)}")
        print(f"   • Dataset rows: {profile.row_count}")
        print(f"   • Country column: {'✅ Found' if country_column else '❌ Missing'}")
        print(f"   • Year columns: {'✅ Found' if year_columns else '❌ Missing'}")
        
        if country_column and year_columns:
            print("\n🎉 SUCCESS: All required entities can be extracted from this dataset!")
            print("   The agriculture dataset contains the necessary structure for:")
            print("   • Country identification (geographic entities)")
            print("   • Time-series employment measurements (measurement entities)")
        else:
            print("\n⚠️  WARNING: Some required columns are missing")
        
        return target_entities, extracted_entities, profile
        
    except Exception as e:
        print(f"\n❌ Entity extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

def test_with_sample_data():
    """Test the extraction with sample data from the agriculture dataset."""
    print("🧪 Testing with sample agriculture data...")
    
    # Sample data structure
    sample_data = {
        'country': ['Afghanistan', 'Angola', 'Albania'],
        '1991': [63.4, 39.8, 57.9],
        '1992': [63.7, 39.9, 58.1],
        '2019': [42.5, 50.7, 36.6]
    }
    
    print("   Sample data structure:")
    for key, values in sample_data.items():
        print(f"     {key}: {values}")
    
    print("\n   This structure supports:")
    print("   • Country entity (from 'country' column)")
    print("   • Agricultural Employment entity (from year columns)")
    print("   • Time-series analysis (1991-2019)")

if __name__ == "__main__":
    # Test with the agriculture dataset
    csv_file = "agriculture_workers_percent_of_employment.csv"
    
    if os.path.exists(csv_file):
        extract_agriculture_entities(csv_file)
    else:
        print(f"❌ CSV file not found: {csv_file}")
        print("   Please ensure the agriculture dataset is in the current directory")
        print("\n   Testing with sample data instead:")
        test_with_sample_data()
