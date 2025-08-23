#!/usr/bin/env python3
"""
Test script to check if the API server can start and if endpoints are accessible
"""

import subprocess
import time
import requests
import sys
import os

def test_server_startup():
    """Test if the server can start without errors"""
    print("Testing server startup...")
    
    try:
        # Change to the API directory
        api_dir = "sources/Api"
        if not os.path.exists(api_dir):
            print(f"API directory not found: {api_dir}")
            return False
        
        # Try to import the main module
        sys.path.insert(0, api_dir)
        try:
            import main
            print("✓ Main module imported successfully")
        except Exception as e:
            print(f"✗ Failed to import main module: {e}")
            return False
        
        # Check if we can create the FastAPI app
        try:
            app = main.app
            print("✓ FastAPI app created successfully")
        except Exception as e:
            print(f"✗ Failed to create FastAPI app: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Server startup test failed: {e}")
        return False

def test_endpoints():
    """Test if the endpoints are accessible"""
    print("\nTesting endpoints...")
    
    base_url = "http://localhost:8000"
    
    # Test public health endpoint
    try:
        response = requests.get(f"{base_url}/health/public", timeout=5)
        if response.status_code == 200:
            print("✓ Public health endpoint accessible")
            print(f"  Response: {response.json()}")
        else:
            print(f"✗ Public health endpoint returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"✗ Public health endpoint test failed: {e}")
        return False
    
    # Test root endpoint
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✓ Root endpoint accessible")
            print(f"  Available endpoints: {list(response.json()['endpoints'].keys())}")
        else:
            print(f"✗ Root endpoint returned status {response.status_code}")
    except Exception as e:
        print(f"✗ Root endpoint test failed: {e}")
    
    return True

def main():
    """Main test function"""
    print("KnowledgeForge API Server Test")
    print("=" * 40)
    
    # Test server startup
    if not test_server_startup():
        print("\n❌ Server startup test failed")
        return
    
    print("\n✅ Server startup test passed")
    
    # Test endpoints
    if not test_endpoints():
        print("\n❌ Endpoint tests failed")
        return
    
    print("\n✅ All tests passed!")
    print("\nTo start the server, run:")
    print("cd sources/Api && python main.py")

if __name__ == "__main__":
    main()
