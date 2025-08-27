#!/usr/bin/env python3
"""Validation test for agriculture dataset entity extraction."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Api'))

from ontology_extractor.profiler import DataProfiler
from ontology_extractor.models import Entity, DataType
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def validate_agriculture_entities():
    """
    Validate that the agriculture dataset can support the two required entities:
    1. Core Entity: Country
    2. Measurement Entity: Agricultural Employment
    """
    print("🌾 Validating Agriculture Dataset Entity Support")
    print("=" * 60)
    
    csv_file = "agriculture_workers_percent_of_employment.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        print("   Please ensure the agriculture dataset is in the current directory")
        return False
    
    try:
        # Step 1: Profile the dataset
        print("1️⃣ Profiling dataset structure...")
        profiler = DataProfiler()
        profile = profiler.profile_dataset(csv_file, sample_size=100)
        
        print(f"   ✅ Dataset loaded: {profile.row_count} rows, {profile.column_count} columns")
        
        # Step 2: Analyze column structure
        print("\n2️⃣ Analyzing column structure...")
        
        # Find country column
        country_column = next((col for col in profile.columns if col.name == 'country'), None)
        
        # Find year columns (1991-2019)
        year_columns = [col for col in profile.columns if col.name.isdigit() and 1991 <= int(col.name) <= 2019]
        
        # Find percentage columns (columns with decimal values)
        percentage_columns = []
        for col in profile.columns:
            if col.name != 'country' and col.data_type == DataType.NUMERICAL:
                # Check if values look like percentages (0-100 range)
                if hasattr(col, 'statistics') and 'min' in col.statistics and 'max' in col.statistics:
                    min_val = col.statistics['min']
                    max_val = col.statistics['max']
                    if min_val >= 0 and max_val <= 100:
                        percentage_columns.append(col)
        
        # Step 3: Validate entity support
        print("\n3️⃣ Validating entity support...")
        
        validation_results = []
        
        # Validate Country entity support
        if country_column:
            validation_results.append({
                'entity': 'Country',
                'status': '✅ SUPPORTED',
                'details': f"Column '{country_column.name}' found with {country_column.data_type.value} data type",
                'sample_values': country_column.sample_values[:3] if hasattr(country_column, 'sample_values') else []
            })
        else:
            validation_results.append({
                'entity': 'Country',
                'status': '❌ NOT SUPPORTED',
                'details': 'No country column found',
                'sample_values': []
            })
        
        # Validate Agricultural Employment entity support
        if year_columns and percentage_columns:
            validation_results.append({
                'entity': 'Agricultural Employment',
                'status': '✅ SUPPORTED',
                'details': f"Found {len(year_columns)} year columns and {len(percentage_columns)} percentage columns",
                'sample_values': [f"{year_columns[0].name}-{year_columns[-1].name}"] if year_columns else []
            })
        else:
            validation_results.append({
                'entity': 'Agricultural Employment',
                'status': '❌ NOT SUPPORTED',
                'details': f"Year columns: {len(year_columns)}, Percentage columns: {len(percentage_columns)}",
                'sample_values': []
            })
        
        # Step 4: Display validation results
        print("\n4️⃣ Validation Results:")
        print("-" * 40)
        
        for result in validation_results:
            print(f"\n   {result['entity']}: {result['status']}")
            print(f"      Details: {result['details']}")
            if result['sample_values']:
                print(f"      Sample: {result['sample_values']}")
        
        # Step 5: Create entity definitions
        print("\n5️⃣ Entity Definitions:")
        print("-" * 40)
        
        entities = []
        
        # Entity 1: Country
        if country_column:
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
            entities.append(country_entity)
            print(f"\n   ✅ Country Entity Created:")
            print(f"      Name: {country_entity.name}")
            print(f"      Type: {country_entity.entity_type}")
            print(f"      Source: {country_entity.source_column}")
            print(f"      Business Meaning: {country_entity.attributes['business_meaning']}")
        
        # Entity 2: Agricultural Employment
        if year_columns:
            agricultural_entity = Entity(
                id="agricultural_employment_measurement",
                name="Agricultural Employment",
                entity_type="measurement_entity",
                attributes={
                    "business_meaning": "Represents the percentage of a country's workforce employed in the agriculture sector for a given year",
                    "year": f"e.g., {', '.join([col.name for col in year_columns[:5]])}...",
                    "percentage": "e.g., 63.4, 39.8",
                    "source_columns": [col.name for col in year_columns],
                    "extraction_method": "agriculture_dataset_mapping",
                    "measurement_unit": "percentage",
                    "measurement_type": "employment_ratio",
                    "entity_category": "measurement_entity",
                    "description": "Time-series measurement of agricultural employment percentages"
                },
                confidence=0.98,
                source_column="measurement_values"
            )
            entities.append(agricultural_entity)
            print(f"\n   ✅ Agricultural Employment Entity Created:")
            print(f"      Name: {agricultural_entity.name}")
            print(f"      Type: {agricultural_entity.entity_type}")
            print(f"      Source: {agricultural_entity.source_column}")
            print(f"      Business Meaning: {agricultural_entity.attributes['business_meaning']}")
            print(f"      Time Range: {year_columns[0].name} to {year_columns[-1].name}")
        
        # Step 6: Final summary
        print("\n" + "=" * 60)
        print("📊 FINAL VALIDATION SUMMARY:")
        print(f"   • Required entities: 2")
        print(f"   • Supported entities: {len(entities)}")
        print(f"   • Dataset structure: {'✅ Valid' if len(entities) == 2 else '❌ Invalid'}")
        
        if len(entities) == 2:
            print("\n🎉 SUCCESS: Agriculture dataset fully supports required entity extraction!")
            print("   You can extract:")
            print("   • Country entities (geographic)")
            print("   • Agricultural Employment entities (time-series measurements)")
            return True
        else:
            print(f"\n⚠️  WARNING: Only {len(entities)} out of 2 required entities are supported")
            return False
            
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = validate_agriculture_entities()
    if success:
        print("\n🚀 Ready to extract entities from agriculture dataset!")
    else:
        print("\n❌ Dataset validation failed - check the issues above")
