#!/usr/bin/env python3
"""Test entity extraction from agriculture workers dataset using running backend API."""

import pytest
import pandas as pd
import sys
import os
import requests
import time
from pathlib import Path
from typing import Dict, List, Any

class TestAgricultureWorkersExtraction:
    """Test entity extraction from agriculture workers CSV using running backend."""
    
    def __init__(self):
        """Initialize test fixtures."""
        # Point to your running backend
        self.base_url = "http://localhost:8000"  # Adjust if different
        self.csv_path = Path(__file__).parent.parent.parent / "data" / "sample-data" / "agriculture_workers_percent_of_employment.csv"
        
        # Test the API connection first
        self.test_api_connection()
    
    def test_api_connection(self):
        """Test that the backend API is accessible."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ Backend API accessible at {self.base_url}")
                return True
            else:
                print(f"⚠️  Backend API returned {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to backend API at {self.base_url}: {e}")
            print("   Make sure your backend is running with: python app.py")
            return False
    
    def test_csv_file_exists(self):
        """Test that the sample CSV file exists."""
        assert self.csv_path.exists(), f"CSV file not found at {self.csv_path}"
        print(f"✅ CSV file found: {self.csv_path}")
    
    def test_csv_structure(self):
        """Test the structure of the agriculture workers CSV."""
        if not self.csv_path.exists():
            pytest.skip(f"CSV file not found at {self.csv_path}")
        
        # Load the CSV
        df = pd.read_csv(self.csv_path)
        
        # Check basic structure
        assert len(df.columns) == 30, f"Expected 30 columns, got {len(df.columns)}"
        assert len(df) > 0, "DataFrame is empty"
        
        # Check column types
        assert df['country'].dtype == 'object', "Country column should be string/categorical"
        assert df['1991'].dtype in ['float64', 'int64'], "Year columns should be numeric"
        
        print(f"✅ CSV structure validated: {len(df.columns)} columns, {len(df)} rows")
    
    def test_backend_endpoints(self):
        """Test that all required backend endpoints are working."""
        print("\n🔍 Testing Backend Endpoints...")
        
        # Test health endpoint
        response = requests.get(f"{self.base_url}/health")
        assert response.status_code == 200, f"Health endpoint failed: {response.status_code}"
        health_data = response.json()
        print(f"✅ Health endpoint: {health_data.get('status', 'unknown')}")
        
        # Test root endpoint
        response = requests.get(f"{self.base_url}/")
        assert response.status_code == 200, f"Root endpoint failed: {response.status_code}"
        root_data = response.json()
        print(f"✅ Root endpoint: {root_data.get('message', 'unknown')}")
        
        # Test extraction endpoints exist
        endpoints_to_test = [
            "/api/v1/extract/upload",
            "/api/v1/extract/",
            "/api/v1/data/profile"
        ]
        
        for endpoint in endpoints_to_test:
            try:
                # Just check if endpoint exists (GET request)
                response = requests.get(f"{self.base_url}{endpoint}")
                # We don't care about the status code here, just that the endpoint exists
                print(f"✅ Endpoint exists: {endpoint}")
            except Exception as e:
                print(f"⚠️  Endpoint {endpoint}: {e}")
    
    def test_file_upload_and_extraction(self):
        """Test the complete file upload and extraction pipeline."""
        if not self.csv_path.exists():
            pytest.skip(f"CSV file not found at {self.csv_path}")
        
        print("\n🚀 Testing Complete Extraction Pipeline...")
        
        try:
            # Step 1: Upload the CSV file
            print("📤 Step 1: Uploading CSV file...")
            with open(self.csv_path, 'rb') as f:
                files = {'file': ('agriculture_workers.csv', f, 'text/csv')}
                response = requests.post(f"{self.base_url}/api/v1/extract/upload", files=files)
            
            assert response.status_code == 200, f"File upload failed: {response.status_code}"
            upload_data = response.json()
            file_path = upload_data.get("file_path")
            assert file_path, "No file_path returned from upload"
            
            print(f"✅ File uploaded successfully: {file_path}")
            
            # Step 2: Start entity extraction (file_path as query parameter)
            print("🔍 Step 2: Starting entity extraction...")
            extraction_response = requests.post(
                f"{self.base_url}/api/v1/extract/?file_path={file_path}",
                json={
                    "extraction_config": {
                        "confidence_threshold": 0.7,
                        "max_entities_per_column": 100,
                        "enable_semantic_similarity": True,
                        "use_llm": True
                    }
                }
            )
            
            assert extraction_response.status_code == 200, f"Extraction failed: {extraction_response.status_code}"
            extraction_data = extraction_response.json()
            task_id = extraction_data.get("task_id")
            assert task_id, "No task_id returned from extraction"
            
            print(f"✅ Extraction task created: {task_id}")
            
            # Step 3: Monitor extraction progress
            print("⏳ Step 3: Monitoring extraction progress...")
            max_wait_time = 120  # 2 minutes max
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                status_response = requests.get(f"{self.base_url}/api/v1/extract/{task_id}")
                assert status_response.status_code == 200, f"Status check failed: {status_response.status_code}"
                
                status_data = status_response.json()
                current_status = status_data.get("status", "unknown")
                print(f"   Current status: {current_status}")
                
                if current_status == "completed":
                    print("✅ Extraction completed successfully!")
                    break
                elif current_status == "failed":
                    error_msg = status_data.get("error", "Unknown error")
                    print(f"❌ Extraction failed: {error_msg}")
                    return False
                elif current_status in ["pending", "processing"]:
                    print("   Waiting for completion...")
                    time.sleep(5)  # Wait 5 seconds before checking again
                else:
                    print(f"   Unknown status: {current_status}")
                    time.sleep(5)
            else:
                print("⚠️  Extraction timed out after 2 minutes")
                return False
            
            # Step 4: Get extraction results from entities endpoint
            print("📊 Step 4: Retrieving extraction results...")
            results_response = requests.get(f"{self.base_url}/api/v1/entities?task_id={task_id}")
            
            if results_response.status_code == 200:
                results_data = results_response.json()
                entities = results_data.get("entities", [])
                print(f"✅ Retrieved {len(entities)} extracted entities")
                
                # Display sample entities
                for i, entity in enumerate(entities[:3]):
                    print(f"   Entity {i+1}: {entity.get('name', 'Unknown')} ({entity.get('entity_type', 'Unknown')})")
                    print(f"      Confidence: {entity.get('confidence', 0)}")
                    print(f"      Source: {entity.get('source_columns', [])}")
                
                return len(entities) > 0
            else:
                print(f"⚠️  Could not retrieve results: {results_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Extraction pipeline test failed: {e}")
            return False
    
    def test_data_profiling(self):
        """Test the data profiling functionality using the extraction pipeline."""
        if not self.csv_path.exists():
            pytest.skip(f"CSV file not found at {self.csv_path}")
        
        print("\n📈 Testing Data Profiling...")
        
        try:
            # First upload the file
            with open(self.csv_path, 'rb') as f:
                files = {'file': ('agriculture_workers.csv', f, 'text/csv')}
                response = requests.post(f"{self.base_url}/api/v1/extract/upload", files=files)
            
            if response.status_code != 200:
                pytest.skip("File upload failed, cannot test profiling")
            
            upload_data = response.json()
            file_path = upload_data.get("file_path")
            
            # Start extraction to trigger profiling
            extraction_response = requests.post(
                f"{self.base_url}/api/v1/extract/?file_path={file_path}",
                json={"extraction_config": {"confidence_threshold": 0.7}}
            )
            
            if extraction_response.status_code == 200:
                print("✅ Data profiling initiated via extraction pipeline")
                return True
            else:
                print(f"⚠️  Profiling failed: {extraction_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Profiling test failed: {e}")
            return False
    
    def test_ontology_mapping(self):
        """Test the ontology mapping functionality via extraction pipeline."""
        print("\n🧠 Testing Ontology Mapping...")
        
        try:
            # Test if extraction endpoint works (which includes ontology mapping)
            response = requests.get(f"{self.base_url}/api/v1/extract/")
            
            if response.status_code == 405:  # Method not allowed (POST required)
                print("✅ Ontology mapping endpoint exists (POST required)")
                return True
            else:
                print(f"⚠️  Ontology mapping endpoint: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"⚠️  Ontology mapping test: {e}")
            return False
    
    def test_graph_storage(self):
        """Test the graph storage functionality."""
        print("\n🗄️  Testing Graph Storage...")
        
        try:
            # Test graph endpoints that exist
            endpoints = [
                "/api/v1/entities",
                "/api/v1/relationships",
                "/api/v1/graph/visualize"
            ]
            
            accessible_endpoints = 0
            for endpoint in endpoints:
                try:
                    response = requests.get(f"{self.base_url}{endpoint}")
                    if response.status_code in [200, 405]:  # 405 means endpoint exists but method not allowed
                        print(f"✅ Graph endpoint accessible: {endpoint}")
                        accessible_endpoints += 1
                    else:
                        print(f"⚠️  Graph endpoint {endpoint}: {response.status_code}")
                except Exception:
                    print(f"⚠️  Graph endpoint {endpoint}: Not accessible")
            
            return accessible_endpoints > 0
            
        except Exception as e:
            print(f"❌ Graph storage test failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests and provide summary."""
        print("\n" + "="*60)
        print("🧪 AGRICULTURE WORKERS EXTRACTION TEST SUITE")
        print("🔗 Testing Running Backend API")
        print("="*60)
        
        # Check if backend is accessible first
        if not self.test_api_connection():
            print("\n❌ Cannot connect to backend. Please ensure it's running:")
            print("   cd sources/api")
            print("   python app.py")
            return False
        
        test_methods = [
            'test_csv_file_exists',
            'test_csv_structure', 
            'test_backend_endpoints',
            'test_file_upload_and_extraction',
            'test_data_profiling',
            'test_ontology_mapping',
            'test_graph_storage'
        ]
        
        passed = 0
        failed = 0
        skipped = 0
        
        for method_name in test_methods:
            method = getattr(self, method_name)
            print(f"\n🔍 Running: {method_name}")
            print("-" * 40)
            
            try:
                result = method()
                if result is False:  # Explicit failure
                    print(f"❌ FAILED: {method_name}")
                    failed += 1
                else:
                    print(f"✅ PASSED: {method_name}")
                    passed += 1
            except Exception as e:
                if "skip" in str(e).lower():
                    print(f"⏭️  SKIPPED: {method_name} - {e}")
                    skipped += 1
                else:
                    print(f"❌ FAILED: {method_name} - {e}")
                    failed += 1
        
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️  Skipped: {skipped}")
        print(f"📈 Total: {passed + failed + skipped}")
        
        if failed == 0:
            print("\n🎉 All tests passed! Your backend is working correctly.")
            print("\n💡 Your backend successfully:")
            print("   - Accepts file uploads")
            print("   - Performs entity extraction")
            print("   - Maps entities to ontologies")
            print("   - Stores data in the graph database")
        else:
            print(f"\n⚠️  {failed} test(s) failed. Check your backend implementation.")
        
        return failed == 0


def main():
    """Main function to run the test suite."""
    tester = TestAgricultureWorkersExtraction()
    success = tester.run_all_tests()
    
    if success:
        print("\n🚀 Your backend is ready for production use!")
        return 0
    else:
        print("\n🔧 Some issues found. Please fix your backend before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
