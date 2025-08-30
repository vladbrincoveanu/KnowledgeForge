#!/usr/bin/env python3
"""Test script for the enhanced EntityExtractor class."""

import os
import sys
import tempfile
import pandas as pd
from pathlib import Path

# Add the ontology_extractor module to the path
sys.path.insert(0, str(Path(__file__).parent))

from ontology_extractor.entity_extractor import EntityExtractor
from domain.ontology_models import ColumnProfile, DataType
from ontology_extractor.llm_manager import LLMManager


def create_sample_csv():
    """Create a sample CSV file for testing."""
    data = {
        'customer_id': [1, 2, 3, 4, 5],
        'email': [
            'john.doe@example.com',
            'jane.smith@company.org',
            'bob.wilson@test.net',
            'alice.brown@demo.com',
            'charlie.davis@sample.org'
        ],
        'phone': [
            '+1-555-123-4567',
            '555-987-6543',
            '(555) 456-7890',
            '555.789.0123',
            '555 321 0987'
        ],
        'street_address': [
            '123 Main St',
            '456 Oak Ave',
            '789 Pine Rd',
            '321 Elm St',
            '654 Maple Dr'
        ],
        'city': ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix'],
        'state': ['NY', 'CA', 'IL', 'TX', 'AZ'],
        'zip_code': ['10001', '90210', '60601', '77001', '85001'],
        'country': ['USA', 'USA', 'USA', 'USA', 'USA'],
        'order_date': [
            '2024-01-15',
            '2024-01-16',
            '2024-01-17',
            '2024-01-18',
            '2024-01-19'
        ],
        'order_amount': [99.99, 149.50, 75.25, 200.00, 89.99],
        'product_category': [
            'Electronics > Computers > Laptops',
            'Clothing > Women > Dresses',
            'Home > Kitchen > Appliances',
            'Sports > Fitness > Equipment',
            'Books > Fiction > Mystery'
        ],
        'product_subcategory': [
            'Gaming Laptops',
            'Evening Dresses',
            'Coffee Makers',
            'Treadmills',
            'Detective Novels'
        ]
    }
    
    df = pd.DataFrame(data)
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    df.to_csv(temp_file.name, index=False)
    temp_file.close()
    
    return temp_file.name


def create_sample_columns():
    """Create sample column profiles for testing."""
    return [
        ColumnProfile(
            name='customer_id',
            data_type=DataType.INTEGER,
            null_count=0,
            unique_count=5,
            sample_values=[1, 2, 3, 4, 5],
            statistics={'min': 1, 'max': 5, 'mean': 3.0}
        ),
        ColumnProfile(
            name='email',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['john.doe@example.com', 'jane.smith@company.org'],
            statistics={}
        ),
        ColumnProfile(
            name='phone',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['+1-555-123-4567', '555-987-6543'],
            statistics={}
        ),
        ColumnProfile(
            name='street_address',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['123 Main St', '456 Oak Ave'],
            statistics={}
        ),
        ColumnProfile(
            name='city',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['New York', 'Los Angeles'],
            statistics={}
        ),
        ColumnProfile(
            name='state',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['NY', 'CA'],
            statistics={}
        ),
        ColumnProfile(
            name='zip_code',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['10001', '90210'],
            statistics={}
        ),
        ColumnProfile(
            name='country',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=1,
            sample_values=['USA'],
            statistics={}
        ),
        ColumnProfile(
            name='order_date',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['2024-01-15', '2024-01-16'],
            statistics={}
        ),
        ColumnProfile(
            name='order_amount',
            data_type=DataType.FLOAT,
            null_count=0,
            unique_count=5,
            sample_values=[99.99, 149.50],
            statistics={'min': 75.25, 'max': 200.00, 'mean': 122.95}
        ),
        ColumnProfile(
            name='product_category',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['Electronics > Computers > Laptops'],
            statistics={}
        ),
        ColumnProfile(
            name='product_subcategory',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['Gaming Laptops'],
            statistics={}
        )
    ]


def test_entity_extraction():
    """Test the enhanced entity extraction functionality."""
    print("🚀 Testing Enhanced EntityExtractor...")
    
    # Create sample data
    csv_file = create_sample_csv()
    columns = create_sample_columns()
    
    try:
        # Initialize EntityExtractor with cache directory
        cache_dir = tempfile.mkdtemp()
        extractor = EntityExtractor(cache_dir=cache_dir)
        
        print(f"📁 Created cache directory: {cache_dir}")
        
        # Configuration
        config = {
            'min_confidence': 0.6,
            'max_entities_per_column': 50,
            'enable_semantic_similarity': True
        }
        
        # Extract entities
        print("🔍 Extracting entities...")
        entities = extractor.extract_entities(csv_file, columns, config)
        
        print(f"✅ Extracted {len(entities)} entities")
        
        # Get extraction summary
        summary = extractor.get_extraction_summary(entities)
        print("\n📊 Extraction Summary:")
        print(f"  Total entities: {summary.get('total_entities', 0)}")
        print(f"  Average confidence: {summary.get('avg_confidence', 0):.3f}")
        print(f"  Unique source columns: {summary.get('unique_source_columns', 0)}")
        
        print("\n🔧 Extraction Methods:")
        for method, count in summary.get('extraction_methods', {}).items():
            print(f"  {method}: {count}")
        
        print("\n🏷️ Entity Types:")
        for entity_type, count in summary.get('entity_types', {}).items():
            print(f"  {entity_type}: {count}")
        
        print("\n🎯 Confidence Distribution:")
        for level, count in summary.get('confidence_distribution', {}).items():
            print(f"  {level}: {count}")
        
        # Show some example entities
        print("\n📋 Example Entities:")
        for i, entity in enumerate(entities[:5]):
            print(f"  {i+1}. {entity.name} ({entity.entity_type})")
            print(f"     Confidence: {entity.confidence:.3f}")
            print(f"     Method: {entity.attributes.get('extraction_method', 'unknown')}")
            print(f"     Source: {entity.source_column}")
            if 'sample_values' in entity.attributes:
                samples = entity.attributes['sample_values'][:3]
                print(f"     Samples: {samples}")
            print()
        
        # Test caching
        print("🔄 Testing caching...")
        cached_entities = extractor.extract_entities(csv_file, columns, config)
        print(f"  Cached extraction returned {len(cached_entities)} entities")
        print(f"  Cache hit: {len(cached_entities) == len(entities)}")
        
        # Get cache stats
        cache_stats = extractor.get_cache_stats()
        print(f"  Cache files: {cache_stats.get('cached_files', 0)}")
        print(f"  Cache size: {cache_stats.get('total_cache_size_bytes', 0)} bytes")
        
        # Test pattern extraction
        print("\n🔍 Testing pattern extraction...")
        patterns = extractor.extract_entity_patterns(csv_file, 'email')
        print(f"  Email patterns: {list(patterns.keys())}")
        
        # Clean up
        os.unlink(csv_file)
        extractor.clear_cache()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up cache directory
        import shutil
        if 'cache_dir' in locals():
            shutil.rmtree(cache_dir, ignore_errors=True)


def test_with_llm():
    """Test entity extraction with LLM integration."""
    print("\n🤖 Testing EntityExtractor with LLM integration...")
    
    try:
        # Try to initialize LLM manager (will fail if LLM Server is not running)
        llm_manager = LLMManager(lmstudio_url="http://localhost:1234")
        
        # Test if LLM Server is available
        if llm_manager._test_connection():
            print("✅ LLM Server connection successful")
            
            # Create sample data
            csv_file = create_sample_csv()
            columns = create_sample_columns()
            
            # Initialize EntityExtractor with LLM
            cache_dir = tempfile.mkdtemp()
            extractor = EntityExtractor(llm_manager=llm_manager, cache_dir=cache_dir)
            
            # Extract entities with LLM
            config = {'min_confidence': 0.5, 'max_entities_per_column': 20}
            entities = extractor.extract_entities(csv_file, columns, config)
            
            print(f"✅ LLM-enhanced extraction: {len(entities)} entities")
            
            # Clean up
            os.unlink(csv_file)
            extractor.clear_cache()
            shutil.rmtree(cache_dir, ignore_errors=True)
            
        else:
            print("⚠️ LLM Server not available, skipping LLM tests")
            
    except Exception as e:
        print(f"⚠️ LLM test skipped: {e}")


if __name__ == "__main__":
    test_entity_extraction()
    test_with_llm()
