#!/usr/bin/env python3
"""
Test script for the KnowledgeForge Ontology Extraction API.

This script tests the main API endpoints to ensure they're working correctly.
"""

import requests
import json
import time
from pathlib import Path

# API configuration
API_BASE_URL = "http://localhost:8000"
API_KEY = "test-api-key-12345"  # This should match your API key validation

def test_health_endpoint():
    """Test the health check endpoint."""
    print("🔍 Testing health endpoint...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        print(f"✅ Health check: {response.status_code}")
        print(f"   Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_ready_endpoint():
    """Test the readiness check endpoint."""
    print("🔍 Testing ready endpoint...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/ready")
        print(f"✅ Ready check: {response.status_code}")
        print(f"   Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Ready check failed: {e}")
        return False

def test_root_endpoint():
    """Test the root endpoint."""
    print("🔍 Testing root endpoint...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/")
        print(f"✅ Root endpoint: {response.status_code}")
        print(f"   Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Root endpoint failed: {e}")
        return False

def test_authentication():
    """Test API authentication."""
    print("🔍 Testing authentication...")
    
    # Test without API key (should fail)
    try:
        response = requests.get(f"{API_BASE_URL}/entities")
        if response.status_code == 401:
            print("✅ Authentication required (no key)")
        else:
            print(f"⚠️  Unexpected status without key: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        return False
    
    # Test with API key (should work)
    try:
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(f"{API_BASE_URL}/entities", headers=headers)
        print(f"✅ Authentication with key: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ Authentication with key failed: {e}")
        return False

def test_extract_endpoint():
    """Test the extract endpoint."""
    print("🔍 Testing extract endpoint...")
    
    # Create a test CSV file
    test_csv_path = create_test_csv()
    
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "file_path": str(test_csv_path),
            "extraction_config": {
                "confidence_threshold": 0.7,
                "max_entities_per_column": 50
            }
        }
        
        response = requests.post(
            f"{API_BASE_URL}/extract",
            headers=headers,
            json=data
        )
        
        print(f"✅ Extract endpoint: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Task ID: {result.get('task_id')}")
            print(f"   Status: {result.get('status')}")
            return result.get('task_id')
        else:
            print(f"   Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Extract endpoint failed: {e}")
        return None
    finally:
        # Clean up test file
        if test_csv_path.exists():
            test_csv_path.unlink()

def test_entities_endpoint():
    """Test the entities endpoint."""
    print("🔍 Testing entities endpoint...")
    
    try:
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(f"{API_BASE_URL}/entities", headers=headers)
        
        print(f"✅ Entities endpoint: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Total entities: {result.get('total_count', 0)}")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Entities endpoint failed: {e}")
        return False

def test_relationships_endpoint():
    """Test the relationships endpoint."""
    print("🔍 Testing relationships endpoint...")
    
    try:
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(f"{API_BASE_URL}/relationships", headers=headers)
        
        print(f"✅ Relationships endpoint: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Total relationships: {result.get('total_count', 0)}")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Relationships endpoint failed: {e}")
        return False

def test_metrics_endpoint():
    """Test the metrics endpoint."""
    print("🔍 Testing metrics endpoint...")
    
    try:
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(f"{API_BASE_URL}/metrics", headers=headers)
        
        print(f"✅ Metrics endpoint: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   System metrics: {result.get('system_metrics', {})}")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Metrics endpoint failed: {e}")
        return False

def test_feedback_endpoint():
    """Test the feedback endpoint."""
    print("🔍 Testing feedback endpoint...")
    
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "entity_id": "test_entity_123",
            "feedback_type": "validate_entity",
            "feedback_value": "correct",
            "confidence_delta": 0.1,
            "user_id": "test_user"
        }
        
        response = requests.post(
            f"{API_BASE_URL}/feedback",
            headers=headers,
            json=data
        )
        
        print(f"✅ Feedback endpoint: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Feedback ID: {result.get('feedback_id')}")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Feedback endpoint failed: {e}")
        return False

def create_test_csv():
    """Create a test CSV file for testing."""
    test_data = """country,year,value
Belarus,2000,15.1
Belarus,2001,15.4
Belarus,2002,15.5
Belarus,2003,15.7
Belarus,2004,15.9"""
    
    test_file = Path("test_data.csv")
    test_file.write_text(test_data)
    return test_file

def run_all_tests():
    """Run all API tests."""
    print("🚀 Starting KnowledgeForge API Tests")
    print("=" * 50)
    
    tests = [
        ("Health Endpoint", test_health_endpoint),
        ("Ready Endpoint", test_ready_endpoint),
        ("Root Endpoint", test_root_endpoint),
        ("Authentication", test_authentication),
        ("Extract Endpoint", test_extract_endpoint),
        ("Entities Endpoint", test_entities_endpoint),
        ("Relationships Endpoint", test_relationships_endpoint),
        ("Metrics Endpoint", test_metrics_endpoint),
        ("Feedback Endpoint", test_feedback_endpoint),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        
        try:
            result = test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
                
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")
            results.append((test_name, False))
        
        time.sleep(0.5)  # Small delay between tests
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the API configuration and logs.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
