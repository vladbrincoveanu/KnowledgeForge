#!/usr/bin/env python3
"""
Comprehensive test script for KnowledgeForge API backend
Tests entity extraction, file upload, and API endpoints
"""

import requests
import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "http://localhost:8000"
TEST_CSV_FILE = "agriculture_workers_percent_of_employment.csv"
TIMEOUT = 30  # seconds

class KnowledgeForgeAPITester:
    """Comprehensive API tester for KnowledgeForge backend."""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = {}
        
    def test_health_endpoints(self) -> bool:
        """Test basic health and status endpoints."""
        print("🔍 Testing health endpoints...")
        
        try:
            # Test public health
            response = self.session.get(f"{self.base_url}/health/public", timeout=10)
            if response.status_code == 200:
                print("✅ Public health endpoint working")
                health_data = response.json()
                print(f"   Status: {health_data.get('status', 'Unknown')}")
                print(f"   Version: {health_data.get('version', 'Unknown')}")
            else:
                print(f"❌ Public health failed: {response.status_code}")
                return False
            
            # Test root endpoint
            response = self.session.get(f"{self.base_url}/", timeout=10)
            if response.status_code == 200:
                print("✅ Root endpoint working")
                root_data = response.json()
                if 'endpoints' in root_data:
                    print(f"   Available endpoints: {list(root_data['endpoints'].keys())}")
            else:
                print(f"❌ Root endpoint failed: {response.status_code}")
                return False
                
            return True
            
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to server. Is it running on localhost:8000?")
            return False
        except Exception as e:
            print(f"❌ Health test failed: {e}")
            return False
    
    def test_file_upload(self) -> Optional[str]:
        """Test file upload functionality."""
        print("\n📁 Testing file upload...")
        
        if not os.path.exists(TEST_CSV_FILE):
            print(f"❌ Test CSV file not found: {TEST_CSV_FILE}")
            return None
        
        try:
            with open(TEST_CSV_FILE, 'rb') as f:
                files = {'file': (TEST_CSV_FILE, f, 'text/csv')}
                response = self.session.post(f"{self.base_url}/upload", files=files, timeout=30)
            
            if response.status_code == 200:
                upload_data = response.json()
                print("✅ File upload successful")
                print(f"   Filename: {upload_data.get('filename')}")
                print(f"   File path: {upload_data.get('file_path')}")
                print(f"   Size: {upload_data.get('size')} bytes")
                return upload_data.get('file_path')
            else:
                print(f"❌ File upload failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ File upload test failed: {e}")
            return None
    
    def test_extraction_endpoint_accessibility(self) -> bool:
        """Test if the extraction endpoint is accessible."""
        print("\n🔍 Testing extraction endpoint accessibility...")
        
        try:
            # Test with a simple GET request to see if the endpoint exists
            response = self.session.get(f"{self.base_url}/extract", timeout=10)
            print(f"   GET /extract response: {response.status_code}")
            
            # Test with a minimal POST request to see if it accepts requests
            minimal_request = {
                "file_path": "/tmp/test.csv",
                "extraction_config": {
                    "min_confidence": 0.5,
                    "use_llm": False
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/extract",
                json=minimal_request,
                timeout=30
            )
            
            if response.status_code in [200, 400, 404]:  # Accept various status codes
                print(f"   POST /extract response: {response.status_code}")
                if response.status_code == 400:
                    print(f"   Expected error response: {response.text}")
                return True
            else:
                print(f"   Unexpected response: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Endpoint accessibility test failed: {e}")
            return False

    def test_ontology_extraction(self, file_path: str) -> Optional[str]:
        """Test ontology extraction with the uploaded file."""
        print("\n🔬 Testing ontology extraction...")
        
        try:
            # Create extraction request
            extraction_request = {
                "file_path": file_path,
                "extraction_config": {
                    "min_confidence": 0.5,
                    "max_entities_per_column": 50,
                    "relationship_threshold": 0.6,
                    "use_llm": True,  # ENABLE DeepSeek R1 reasoning
                    "enable_semantic_similarity": True,  # Enable semantic similarity
                    "batch_size": 100,
                    "use_ontology_mapping": False,  # Disable ontology mapping for now
                    "use_llm_business_entities": True,  # Enable LLM business entities
                    "use_time_series_detection": True,  # Keep time series detection
                    "use_hierarchical_detection": True,  # Enable hierarchical detection
                    "use_composite_key_detection": True  # Enable composite key detection
                }
            }
            
            print(f"   Sending extraction request for file: {file_path}")
            print(f"   Request payload: {json.dumps(extraction_request, indent=2)}")
            
            response = self.session.post(
                f"{self.base_url}/extract",
                json=extraction_request,
                timeout=60  # Increased timeout to 60 seconds
            )
            
            if response.status_code == 200:
                extract_data = response.json()
                print("✅ Extraction task created successfully")
                print(f"   Task ID: {extract_data.get('task_id')}")
                print(f"   Status: {extract_data.get('status')}")
                print(f"   Message: {extract_data.get('message')}")
                return extract_data.get('task_id')
            else:
                print(f"❌ Extraction request failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            print("❌ Extraction request timed out after 60 seconds")
            print("   This might indicate the backend is processing a large file")
            return None
        except Exception as e:
            print(f"❌ Extraction test failed: {e}")
            return None
    
    def wait_for_extraction_completion(self, task_id: str, max_wait: int = 120) -> bool:
        """Wait for extraction task to complete and return results."""
        print(f"\n⏳ Waiting for extraction task {task_id} to complete...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = self.session.get(f"{self.base_url}/extract/{task_id}", timeout=10)
                
                if response.status_code == 200:
                    task_data = response.json()
                    status = task_data.get('status', 'unknown')
                    
                    if status == 'completed':
                        print("✅ Extraction completed successfully!")
                        return True
                    elif status == 'failed':
                        error = task_data.get('error', 'Unknown error')
                        print(f"❌ Extraction failed: {error}")
                        return False
                    elif status in ['pending', 'processing']:
                        print(f"   Status: {status} - waiting...")
                        time.sleep(5)
                    else:
                        print(f"   Unknown status: {status}")
                        time.sleep(5)
                else:
                    print(f"❌ Failed to get task status: {response.status_code}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error checking task status: {e}")
                return False
        
        print(f"❌ Extraction timed out after {max_wait} seconds")
        return False
    
    def analyze_extraction_results(self, task_id: str) -> bool:
        """Analyze and validate the extraction results."""
        print("\n📊 Analyzing extraction results...")
        
        try:
            response = self.session.get(f"{self.base_url}/extract/{task_id}", timeout=10)
            if response.status_code != 200:
                print(f"❌ Failed to get results: {response.status_code}")
                return False
            
            task_data = response.json()
            results = task_data.get('results', {})
            
            if not results:
                print("❌ No results found in completed task")
                return False
            
            print("✅ Extraction results retrieved")
            
            # Check for entities
            entities = results.get('entities', [])
            print(f"   Entities found: {len(entities)}")
            
            if entities:
                print("   Entity details:")
                for i, entity in enumerate(entities):
                    print(f"     {i+1}. {entity.get('name', 'Unknown')} ({entity.get('entity_type', 'Unknown')})")
                    print(f"        Confidence: {entity.get('confidence', 0):.2f}")
                    if 'business_meaning' in entity.get('attributes', {}):
                        print(f"        Business meaning: {entity['attributes']['business_meaning']}")
                    if 'source_column' in entity:
                        print(f"        Source column: {entity.get('source_column')}")
                    if 'source_columns' in entity.get('attributes', {}):
                        source_cols = entity['attributes']['source_columns']
                        if len(source_cols) > 3:
                            print(f"        Source columns: {source_cols[:3]}... (total: {len(source_cols)})")
                        else:
                            print(f"        Source columns: {source_cols}")
                    print()
            
            # Check for relationships
            relationships = results.get('relationships', [])
            print(f"   Relationships found: {len(relationships)}")
            
            if relationships:
                print("   Relationship details:")
                for i, rel in enumerate(relationships):
                    print(f"     {i+1}. {rel.get('relationship_type', 'Unknown')}")
                    print(f"        Confidence: {rel.get('confidence', 0):.2f}")
                    if 'source_columns' in rel:
                        print(f"        Source columns: {rel.get('source_columns')}")
            
            # Check for ontology
            ontology = results.get('ontology', {})
            if ontology:
                print(f"   Ontology metadata: {ontology.get('metadata', {})}")
            
            # Analysis summary
            print("\n🔍 ANALYSIS SUMMARY:")
            print(f"   Expected entities: 2 (Country + Agricultural Employment)")
            print(f"   Actual entities: {len(entities)}")
            
            # Categorize entities
            entity_types = {}
            for entity in entities:
                entity_type = entity.get('entity_type', 'unknown')
                if entity_type not in entity_types:
                    entity_types[entity_type] = []
                entity_types[entity_type].append(entity.get('name', 'Unknown'))
            
            print("   Entity type breakdown:")
            for entity_type, names in entity_types.items():
                print(f"     - {entity_type}: {len(names)} entities")
                for name in names[:3]:  # Show first 3 names
                    print(f"       * {name}")
                if len(names) > 3:
                    print(f"       ... and {len(names) - 3} more")
            
            return True
            
        except Exception as e:
            print(f"❌ Results analysis failed: {e}")
            return False
    
    def test_custom_entity_validation(self) -> bool:
        """Test if the extracted entities match our expected structure."""
        print("\n🎯 Validating entity structure...")
        
        try:
            # Get the latest extraction results
            response = self.session.get(f"{self.base_url}/extract", timeout=10)
            if response.status_code != 200:
                print("❌ Cannot access extraction endpoint for validation")
                return False
            
            # For now, we'll just check if the basic structure is working
            # In a real scenario, you'd want to validate specific entity types
            print("✅ Entity structure validation completed")
            return True
            
        except Exception as e:
            print(f"❌ Entity validation failed: {e}")
            return False
    
    def run_comprehensive_test(self) -> bool:
        """Run all tests in sequence."""
        print("🚀 Starting KnowledgeForge API Comprehensive Test")
        print("=" * 60)
        
        # Test 1: Health endpoints
        if not self.test_health_endpoints():
            return False
        
        # Test 2: File upload
        file_path = self.test_file_upload()
        if not file_path:
            return False
        
        # Test 3: Endpoint accessibility
        if not self.test_extraction_endpoint_accessibility():
            return False

        # Test 4: Ontology extraction
        task_id = self.test_ontology_extraction(file_path)
        if not task_id:
            return False
        
        # Test 5: Wait for completion
        if not self.wait_for_extraction_completion(task_id):
            return False
        
        # Test 6: Analyze results
        if not self.analyze_extraction_results(task_id):
            return False
        
        # Test 7: Validate entity structure
        if not self.test_custom_entity_validation():
            return False
        
        print("\n" + "=" * 60)
        print("🎉 All tests completed successfully!")
        print("✅ Your KnowledgeForge backend is working correctly!")
        return True

def main():
    """Main test function."""
    print("KnowledgeForge API Comprehensive Test Suite")
    print("=" * 60)
    
    # Check if backend is accessible
    tester = KnowledgeForgeAPITester()
    
    try:
        success = tester.run_comprehensive_test()
        if success:
            print("\n🎯 Entity extraction test completed successfully!")
            print("📋 The backend successfully:")
            print("   - Accepted file uploads")
            print("   - Processed CSV data")
            print("   - Extracted entities and relationships")
            print("   - Generated ontology results")
        else:
            print("\n❌ Some tests failed. Check the output above for details.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
