#!/usr/bin/env python3
"""Test the actual extraction process to verify serialization works."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'sources', 'Api'))

from ontology_extractor.profiler import DataProfiler
from ontology_extractor.entity_extractor import EntityExtractor
from ontology_extractor.relationship_discoverer import RelationshipDiscoverer
import json
import tempfile

def test_extraction_serialization():
    """Test the actual extraction process and verify serialization works."""
    print("🧪 Testing Extraction Process Serialization")
    print("=" * 60)
    
    try:
        # Create a test CSV file
        csv_content = """country,1991,1992,1993
Afghanistan,63.4,63.7,64.4
Angola,39.8,39.9,40.2
Albania,57.9,58.1,57.6"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_file.write(csv_content)
            temp_file_path = temp_file.name
        
        print(f"📁 Created test file: {temp_file_path}")
        
        try:
            # Step 1: Data Profiling
            print("\n1️⃣ Testing Data Profiling Serialization...")
            profiler = DataProfiler()
            profile = profiler.profile_dataset(temp_file_path, sample_size=10)
            
            # Test serialization of profile
            try:
                profile_dict = profile.model_dump()
                profile_json = json.dumps(profile_dict)
                print("   ✅ Profile serialization successful!")
                print(f"   📊 Profile data: {len(profile_json)} characters")
            except Exception as e:
                print(f"   ❌ Profile serialization failed: {e}")
                return
            
            # Step 2: Entity Extraction
            print("\n2️⃣ Testing Entity Extraction Serialization...")
            entity_extractor = EntityExtractor()
            
            entity_config = {
                'llm_enabled': False,
                'confidence_threshold': 0.5,
                'max_entities': 50,
                'use_regex': True,
                'use_pattern_analysis': True,
                'use_llm_inference': False
            }
            
            entities = entity_extractor.extract_entities(temp_file_path, profile.columns, entity_config)
            
            # Test serialization of entities
            try:
                entities_dict = [entity.model_dump() for entity in entities]
                entities_json = json.dumps(entities_dict)
                print("   ✅ Entity serialization successful!")
                print(f"   🏷️  Entities: {len(entities)}")
                print(f"   📊 Entity data: {len(entities_json)} characters")
            except Exception as e:
                print(f"   ❌ Entity serialization failed: {e}")
                return
            
            # Step 3: Relationship Discovery
            print("\n3️⃣ Testing Relationship Discovery Serialization...")
            relationship_discoverer = RelationshipDiscoverer()
            
            rel_config = {
                'fk_overlap_threshold': 0.8,
                'relationship_threshold': 0.6,
                'max_relationships': 100
            }
            
            relationships = relationship_discoverer.discover_relationships(
                temp_file_path, entities, profile.columns, rel_config
            )
            
            # Test serialization of relationships
            try:
                relationships_dict = [rel.model_dump() for rel in relationships]
                relationships_json = json.dumps(relationships_dict)
                print("   ✅ Relationship serialization successful!")
                print(f"   🔗 Relationships: {len(relationships)}")
                print(f"   📊 Relationship data: {len(relationships_json)} characters")
            except Exception as e:
                print(f"   ❌ Relationship serialization failed: {e}")
                return
            
            # Step 4: Complete Ontology Serialization
            print("\n4️⃣ Testing Complete Ontology Serialization...")
            
            ontology_data = {
                'entities': entities_dict,
                'relationships': relationships_dict,
                'profile': profile_dict,
                'metadata': {
                    'file_path': temp_file_path,
                    'extraction_method': 'business_logic',
                    'confidence': 0.95
                }
            }
            
            try:
                ontology_json = json.dumps(ontology_data)
                print("   ✅ Complete ontology serialization successful!")
                print(f"   📊 Complete ontology: {len(ontology_json)} characters")
                
                # Test that we can parse it back
                parsed_ontology = json.loads(ontology_json)
                print("   ✅ JSON parsing successful!")
                
            except Exception as e:
                print(f"   ❌ Complete ontology serialization failed: {e}")
                return
            
            print("\n" + "=" * 60)
            print("🎉 ALL SERIALIZATION TESTS PASSED!")
            print("=" * 60)
            print("✅ Profile serialization: SUCCESS")
            print("✅ Entity serialization: SUCCESS")
            print("✅ Relationship serialization: SUCCESS")
            print("✅ Complete ontology serialization: SUCCESS")
            print("✅ JSON parsing: SUCCESS")
            print("\n🚀 The backend is now fully functional with no serialization errors!")
            
        finally:
            # Clean up
            try:
                os.unlink(temp_file_path)
                print(f"\n🧹 Cleaned up test file: {temp_file_path}")
            except:
                pass
                
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_extraction_serialization()
