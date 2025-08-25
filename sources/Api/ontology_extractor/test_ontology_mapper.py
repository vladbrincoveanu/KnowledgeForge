"""Test file for OntologyMapper functionality."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ontology_extractor.ontology_mapper import OntologyMapper, StandardOntology
from ontology_extractor.models import Entity, Relationship, DataType
from ontology_extractor.llm_manager import LLMManager


def test_ontology_mapper():
    """Test the OntologyMapper class functionality."""
    
    print("🧪 Testing OntologyMapper...")
    
    # Initialize LLM manager (optional)
    llm_manager = None
    try:
        llm_manager = LLMManager()
    except Exception as e:
        print(f"⚠️  LLM manager not available: {e}")
    
    # Initialize ontology mapper
    mapper = OntologyMapper(llm_manager=llm_manager, use_embeddings=True)
    
    print(f"✅ Initialized OntologyMapper with {len(mapper.standard_ontologies)} standard ontologies")
    
    # Create sample entities
    entities = [
        Entity(
            id="customer_001",
            name="John Doe",
            entity_type="Customer",
            attributes={
                "email": "john.doe@example.com",
                "phone": "+1-555-1234",
                "address": "123 Main St, City, State",
                "registration_date": "2023-01-15"
            },
            confidence=0.95,
            source_column="customer_name"
        ),
        Entity(
            id="product_001",
            name="Laptop Computer",
            entity_type="Product",
            attributes={
                "category": "Electronics",
                "brand": "TechCorp",
                "price": 999.99,
                "description": "High-performance laptop for professionals"
            },
            confidence=0.92,
            source_column="product_name"
        ),
        Entity(
            id="order_001",
            name="Order #12345",
            entity_type="Order",
            attributes={
                "order_date": "2023-02-20",
                "total_amount": 1299.98,
                "status": "completed",
                "shipping_address": "123 Main St, City, State"
            },
            confidence=0.88,
            source_column="order_id"
        )
    ]
    
    # Create sample relationships
    relationships = [
        Relationship(
            id="rel_001",
            name="purchased",
            source_entity="customer_001",
            target_entity="order_001",
            relationship_type="purchase",
            confidence=0.85,
            source_columns=["customer_id", "order_id"]
        ),
        Relationship(
            id="rel_002",
            name="contains",
            source_entity="order_001",
            target_entity="product_001",
            relationship_type="containment",
            confidence=0.90,
            source_columns=["order_id", "product_id"]
        )
    ]
    
    print(f"✅ Created {len(entities)} sample entities and {len(relationships)} relationships")
    
    # Test ontology mapping
    print("\n🔍 Testing entity-to-ontology mapping...")
    
    mapping_result = mapper.map_entities_to_ontologies(entities, relationships)
    
    print(f"✅ Mapping completed in {mapping_result.processing_time:.2f} seconds")
    print(f"📊 Mapping results:")
    print(f"   - Total entities: {mapping_result.mapping_metadata['total_entities']}")
    print(f"   - Mapped entities: {mapping_result.mapping_metadata['mapped_count']}")
    print(f"   - Unmapped entities: {mapping_result.mapping_metadata['unmapped_count']}")
    print(f"   - Average confidence: {mapping_result.mapping_metadata['average_confidence']:.2f}")
    
    # Show detailed mappings
    print("\n📋 Detailed entity mappings:")
    for entity in mapping_result.mapped_entities:
        print(f"   - {entity['entity_name']} ({entity['entity_type']}) → {entity['ontology_class']} in {entity['ontology_name']} (confidence: {entity['confidence']:.2f})")
    
    # Test custom ontology extension
    print("\n🔧 Testing custom ontology extension...")
    
    custom_ontology = mapper.generate_custom_ontology_extension(
        mapping_result.mapped_entities,
        mapping_result.unmapped_entities
    )
    
    print(f"✅ Generated custom ontology with {len(custom_ontology['classes'])} classes and {len(custom_ontology['properties'])} properties")
    
    # Test RDF generation
    print("\n📝 Testing RDF generation...")
    
    rdf_output = mapper.create_rdf_triples(
        mapping_result.mapped_entities,
        custom_ontology
    )
    
    print(f"✅ Generated RDF output ({len(rdf_output)} characters)")
    print("📄 RDF Preview (first 500 chars):")
    print(rdf_output[:500] + "..." if len(rdf_output) > 500 else rdf_output)
    
    # Test ontology validation
    print("\n✅ Testing ontology validation...")
    
    validation_results = mapper.validate_ontology_consistency(
        mapping_result.mapped_entities,
        custom_ontology
    )
    
    print(f"   - Is consistent: {validation_results['is_consistent']}")
    print(f"   - Warnings: {len(validation_results['warnings'])}")
    print(f"   - Errors: {len(validation_results['errors'])}")
    print(f"   - Suggestions: {len(validation_results['suggestions'])}")
    
    if validation_results['warnings']:
        print("   ⚠️  Warnings:")
        for warning in validation_results['warnings']:
            print(f"      - {warning}")
    
    if validation_results['errors']:
        print("   ❌ Errors:")
        for error in validation_results['errors']:
            print(f"      - {error}")
    
    if validation_results['suggestions']:
        print("   💡 Suggestions:")
        for suggestion in validation_results['suggestions']:
            print(f"      - {suggestion}")
    
    # Test OWL export
    print("\n🦉 Testing OWL export...")
    
    owl_output = mapper.export_owl_format(
        mapping_result.mapped_entities,
        custom_ontology,
        output_format="xml"
    )
    
    if owl_output:
        print(f"✅ Generated OWL output ({len(owl_output)} characters)")
        print("📄 OWL Preview (first 500 chars):")
        print(owl_output[:500] + "..." if len(owl_output) > 500 else owl_output)
    else:
        print("⚠️  OWL export failed")
    
    # Test saving and loading
    print("\n💾 Testing save/load functionality...")
    
    test_file = "test_mapping_results.json"
    if mapper.save_mapping_results(mapping_result, test_file):
        print(f"✅ Saved mapping results to {test_file}")
        
        # Load the results back
        loaded_results = mapper.load_mapping_results(test_file)
        if loaded_results:
            print(f"✅ Successfully loaded mapping results from {test_file}")
            print(f"   - Loaded {len(loaded_results.mapped_entities)} mapped entities")
            print(f"   - Loaded {len(loaded_results.unmapped_entities)} unmapped entities")
        else:
            print("❌ Failed to load mapping results")
        
        # Clean up test file
        try:
            os.remove(test_file)
            print(f"🧹 Cleaned up test file {test_file}")
        except Exception as e:
            print(f"⚠️  Could not clean up test file: {e}")
    else:
        print("❌ Failed to save mapping results")
    
    print("\n🎉 OntologyMapper testing completed successfully!")


def test_standard_ontologies():
    """Test the StandardOntology class."""
    
    print("\n🧪 Testing StandardOntology...")
    
    # Create a test ontology
    test_ontology = StandardOntology("TestOntology", "http://test.ontology/", "test")
    
    # Add classes
    test_ontology.add_class("TestClass", {
        "description": "A test class",
        "properties": ["name", "description"],
        "superclass": "Thing"
    })
    
    test_ontology.add_property("testProperty", {
        "type": "string",
        "description": "A test property"
    })
    
    test_ontology.add_hierarchy("Thing", ["TestClass"])
    
    print(f"✅ Created test ontology:")
    print(f"   - Name: {test_ontology.name}")
    print(f"   - Namespace: {test_ontology.namespace}")
    print(f"   - Classes: {list(test_ontology.classes.keys())}")
    print(f"   - Properties: {list(test_ontology.properties.keys())}")
    print(f"   - Hierarchy: {test_ontology.hierarchy}")


if __name__ == "__main__":
    print("🚀 Starting OntologyMapper Tests\n")
    
    try:
        test_standard_ontologies()
        test_ontology_mapper()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
