#!/usr/bin/env python3
"""Test script for the enhanced RelationshipDiscoverer class."""

import os
import sys
import tempfile
import pandas as pd
from pathlib import Path

# Add the ontology_extractor module to the path
sys.path.insert(0, str(Path(__file__).parent))

from ontology_extractor.relationship_discoverer import RelationshipDiscoverer
from ontology_extractor.entity_extractor import EntityExtractor
from ontology_extractor.models import ColumnProfile, DataType, Entity, Relationship
from ontology_extractor.llm_manager import LLMManager


def create_sample_csv():
    """Create a sample CSV file for testing relationships."""
    data = {
        'customer_id': [1, 2, 3, 4, 5, 1, 2, 3, 4, 5],  # Duplicate IDs for relationship testing
        'order_id': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
        'product_id': [201, 202, 203, 204, 205, 201, 202, 203, 204, 205],  # Duplicate products
        'customer_name': ['John Doe', 'Jane Smith', 'Bob Wilson', 'Alice Brown', 'Charlie Davis'] * 2,
        'customer_email': [
            'john@example.com', 'jane@company.org', 'bob@test.net', 
            'alice@demo.com', 'charlie@sample.org'
        ] * 2,
        'order_date': [
            '2024-01-15', '2024-01-16', '2024-01-17', '2024-01-18', '2024-01-19'
        ] * 2,
        'order_amount': [99.99, 149.50, 75.25, 200.00, 89.99] * 2,
        'product_category': [
            'Electronics > Computers > Laptops',
            'Clothing > Women > Dresses',
            'Home > Kitchen > Appliances',
            'Sports > Fitness > Equipment',
            'Books > Fiction > Mystery'
        ] * 2,
        'product_subcategory': [
            'Gaming Laptops',
            'Evening Dresses',
            'Coffee Makers',
            'Treadmills',
            'Detective Novels'
        ] * 2,
        'shipping_address': [
            '123 Main St, New York, NY 10001',
            '456 Oak Ave, Los Angeles, CA 90210',
            '789 Pine Rd, Chicago, IL 60601',
            '321 Elm St, Houston, TX 77001',
            '654 Maple Dr, Phoenix, AZ 85001'
        ] * 2,
        'billing_address': [
            '123 Main St, New York, NY 10001',
            '456 Oak Ave, Los Angeles, CA 90210',
            '789 Pine Rd, Chicago, IL 60601',
            '321 Elm St, Houston, TX 77001',
            '654 Maple Dr, Phoenix, AZ 85001'
        ] * 2
    }
    
    df = pd.DataFrame(data)
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    df.to_csv(temp_file.name, index=False)
    temp_file.close()
    
    return temp_file.name


def create_sample_entities():
    """Create sample entities for testing relationships."""
    return [
        Entity(
            id="customer_1",
            name="John Doe",
            entity_type="person",
            attributes={"source_column": "customer_name", "extraction_method": "llm_inference"},
            confidence=0.9,
            source_column="customer_name",
            source_value="John Doe"
        ),
        Entity(
            id="customer_2",
            name="Jane Smith",
            entity_type="person",
            attributes={"source_column": "customer_name", "extraction_method": "llm_inference"},
            confidence=0.9,
            source_column="customer_name",
            source_value="Jane Smith"
        ),
        Entity(
            id="email_1",
            name="john@example.com",
            entity_type="email",
            attributes={"source_column": "customer_email", "extraction_method": "regex_pattern"},
            confidence=0.95,
            source_column="customer_email",
            source_value="john@example.com"
        ),
        Entity(
            id="product_1",
            name="Gaming Laptops",
            entity_type="product",
            attributes={"source_column": "product_subcategory", "extraction_method": "llm_inference"},
            confidence=0.85,
            source_column="product_subcategory",
            source_value="Gaming Laptops"
        ),
        Entity(
            id="category_1",
            name="Electronics > Computers > Laptops",
            entity_type="hierarchical_category",
            attributes={"source_column": "product_category", "extraction_method": "hierarchical_detection"},
            confidence=0.9,
            source_column="product_category",
            source_value="Electronics > Computers > Laptops"
        ),
        Entity(
            id="address_1",
            name="123 Main St, New York, NY 10001",
            entity_type="location",
            attributes={"source_column": "shipping_address", "extraction_method": "llm_inference"},
            confidence=0.8,
            source_column="shipping_address",
            source_value="123 Main St, New York, NY 10001"
        )
    ]


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
            name='order_id',
            data_type=DataType.INTEGER,
            null_count=0,
            unique_count=10,
            sample_values=[101, 102, 103, 104, 105],
            statistics={'min': 101, 'max': 110, 'mean': 105.5}
        ),
        ColumnProfile(
            name='product_id',
            data_type=DataType.INTEGER,
            null_count=0,
            unique_count=5,
            sample_values=[201, 202, 203, 204, 205],
            statistics={'min': 201, 'max': 205, 'mean': 203.0}
        ),
        ColumnProfile(
            name='customer_name',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['John Doe', 'Jane Smith'],
            statistics={}
        ),
        ColumnProfile(
            name='customer_email',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['john@example.com', 'jane@company.org'],
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
            name='product_category',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['Electronics > Computers > Laptops'],
            statistics={}
        ),
        ColumnProfile(
            name='shipping_address',
            data_type=DataType.STRING,
            null_count=0,
            unique_count=5,
            sample_values=['123 Main St, New York, NY 10001'],
            statistics={}
        )
    ]


def test_relationship_discovery():
    """Test the enhanced relationship discovery functionality."""
    print("🚀 Testing Enhanced RelationshipDiscoverer...")
    
    # Create sample data
    csv_file = create_sample_csv()
    entities = create_sample_entities()
    columns = create_sample_columns()
    
    try:
        # Initialize RelationshipDiscoverer with SBERT support
        discoverer = RelationshipDiscoverer(use_sbert=True)
        
        print("✅ RelationshipDiscoverer initialized with SBERT support")
        
        # Configuration
        config = {
            'relationship_threshold': 0.5,
            'fk_overlap_threshold': 0.7,
            'semantic_similarity_threshold': 0.6
        }
        
        # Discover relationships
        print("🔍 Discovering relationships...")
        relationships = discoverer.discover_relationships(csv_file, entities, columns, config)
        
        print(f"✅ Discovered {len(relationships)} relationships")
        
        # Get relationship statistics
        stats = discoverer.get_relationship_statistics(relationships)
        print("\n📊 Relationship Statistics:")
        print(f"  Total relationships: {stats.get('total_relationships', 0)}")
        print(f"  Average confidence: {stats.get('average_confidence', 0):.3f}")
        
        print("\n🔧 Extraction Methods:")
        for method, count in stats.get('extraction_methods', {}).items():
            print(f"  {method}: {count}")
        
        print("\n🏷️ Relationship Types:")
        for rel_type, count in stats.get('relationship_types', {}).items():
            print(f"  {rel_type}: {count}")
        
        print("\n🎯 Cardinality Distribution:")
        for cardinality, count in stats.get('cardinality_distribution', {}).items():
            print(f"  {cardinality}: {count}")
        
        # Show some example relationships
        print("\n📋 Example Relationships:")
        for i, relationship in enumerate(relationships[:5]):
            print(f"  {i+1}. {relationship.relationship_type}")
            print(f"     Source: {relationship.source_entity_id}")
            print(f"     Target: {relationship.target_entity_id}")
            print(f"     Confidence: {relationship.confidence:.3f}")
            print(f"     Method: {relationship.attributes.get('extraction_method', 'unknown')}")
            if 'cardinality' in relationship.attributes:
                print(f"     Cardinality: {relationship.attributes['cardinality']}")
            print()
        
        # Test relationship evidence
        if relationships:
            print("🔍 Testing relationship evidence...")
            evidence = discoverer.get_relationship_evidence(relationships[0], csv_file)
            print(f"  Evidence keys: {list(evidence.keys())}")
        
        # Test graph export
        print("📊 Testing graph export...")
        graph_data = discoverer.export_relationships_to_graph(relationships, entities)
        print(f"  Graph nodes: {len(graph_data['nodes'])}")
        print(f"  Graph edges: {len(graph_data['edges'])}")
        print(f"  Node types: {list(graph_data['metadata']['node_types'].keys())}")
        print(f"  Edge types: {list(graph_data['metadata']['edge_types'].keys())}")
        
        # Test validation
        print("✅ Testing relationship validation...")
        validation = discoverer.validate_relationships(relationships, entities)
        print(f"  Valid relationships: {validation['valid_relationships']}")
        print(f"  Invalid relationships: {validation['invalid_relationships']}")
        print(f"  Validity rate: {validation['quality_metrics'].get('validity_rate', 0):.3f}")
        
        # Clean up
        os.unlink(csv_file)
        
        print("\n✅ All relationship discovery tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


def test_with_llm():
    """Test relationship discovery with LLM integration."""
    print("\n🤖 Testing RelationshipDiscoverer with LLM integration...")
    
    try:
        # Try to initialize LLM manager (will fail if LLM Server is not running)
        llm_manager = LLMManager(lmstudio_url="http://localhost:1234")

        # Test if LLM Server is available
        if llm_manager._test_connection():
            print("✅ LLM Server connection successful")
            
            # Create sample data
            csv_file = create_sample_csv()
            entities = create_sample_entities()
            columns = create_sample_columns()
            
            # Initialize RelationshipDiscoverer with LLM
            discoverer = RelationshipDiscoverer(
                llm_manager=llm_manager,
                use_sbert=True
            )
            
            # Discover relationships with LLM
            config = {'relationship_threshold': 0.4, 'fk_overlap_threshold': 0.6}
            relationships = discoverer.discover_relationships(csv_file, entities, columns, config)
            
            print(f"✅ LLM-enhanced relationship discovery: {len(relationships)} relationships")
            
            # Show LLM-discovered relationships
            llm_relationships = [r for r in relationships if r.attributes.get('extraction_method') == 'llm_inference']
            if llm_relationships:
                print(f"  LLM-discovered relationships: {len(llm_relationships)}")
                for rel in llm_relationships[:3]:
                    print(f"    - {rel.relationship_type} (confidence: {rel.confidence:.3f})")
            
            # Clean up
            os.unlink(csv_file)
            
        else:
            print("⚠️ LLM Server not available, skipping LLM tests")
            
    except Exception as e:
        print(f"⚠️ LLM test skipped: {e}")


def test_foreign_key_detection():
    """Test foreign key relationship detection specifically."""
    print("\n🔑 Testing Foreign Key Detection...")
    
    # Create sample data with clear foreign key relationships
    data = {
        'customer_id': [1, 2, 3, 4, 5],
        'order_id': [101, 102, 103, 104, 105],
        'customer_name': ['John', 'Jane', 'Bob', 'Alice', 'Charlie'],
        'order_amount': [100, 200, 150, 300, 250]
    }
    
    df = pd.DataFrame(data)
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    df.to_csv(temp_file.name, index=False)
    temp_file.close()
    
    try:
        # Create entities for testing
        entities = [
            Entity(
                id="customer_1",
                name="customer_entity",
                entity_type="identifier",
                attributes={"source_column": "customer_id"},
                confidence=0.9,
                source_column="customer_id",
                source_value="1"
            ),
            Entity(
                id="order_1",
                name="order_entity",
                entity_type="identifier",
                attributes={"source_column": "order_id"},
                confidence=0.9,
                source_column="order_id",
                source_value="101"
            )
        ]
        
        columns = [
            ColumnProfile(name='customer_id', data_type=DataType.INTEGER, null_count=0, unique_count=5, sample_values=[1, 2, 3], statistics={}),
            ColumnProfile(name='order_id', data_type=DataType.INTEGER, null_count=0, unique_count=5, sample_values=[101, 102, 103], statistics={}),
            ColumnProfile(name='customer_name', data_type=DataType.STRING, null_count=0, unique_count=5, sample_values=['John', 'Jane'], statistics={}),
            ColumnProfile(name='order_amount', data_type=DataType.FLOAT, null_count=0, unique_count=5, sample_values=[100, 200], statistics={})
        ]
        
        # Initialize discoverer
        discoverer = RelationshipDiscoverer()
        
        # Test foreign key detection
        config = {'relationship_threshold': 0.5, 'fk_overlap_threshold': 0.7}
        relationships = discoverer.discover_relationships(temp_file.name, entities, columns, config)
        
        # Find foreign key relationships
        fk_relationships = [r for r in relationships if 'foreign_key_analysis' in r.attributes.get('extraction_method', '')]
        
        print(f"  Discovered {len(fk_relationships)} foreign key relationships")
        
        for rel in fk_relationships:
            print(f"    - {rel.relationship_type}: {rel.attributes.get('source_column')} -> {rel.attributes.get('target_column')}")
            print(f"      Overlap: {rel.attributes.get('overlap_percentage', 0):.2%}")
            print(f"      Confidence: {rel.confidence:.3f}")
        
        # Clean up
        os.unlink(temp_file.name)
        
        print("✅ Foreign key detection test completed")
        
    except Exception as e:
        print(f"❌ Foreign key test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_relationship_discovery()
    test_with_llm()
    test_foreign_key_detection()
