#!/usr/bin/env python3
"""
Simple test script to debug API startup issues.
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all imports step by step."""
    print("Testing imports...")
    
    try:
        print("1. Testing basic imports...")
        from Api.Domain.models import DataType, ColumnMetadata
        print("   ✓ Domain models imported")
        
        from Api.Domain.dtos import ProcessFileRequest
        print("   ✓ Domain DTOs imported")
        
        from Api.Infrastructure.mongodb_connector import MongoDBConnector
        print("   ✓ MongoDB connector imported")
        
        from Api.Application.services import DataProcessingService, QueryService
        print("   ✓ Application services imported")
        
        from Api.Api.main import app
        print("   ✓ FastAPI app imported")
        
        print("All imports successful!")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mongodb_connection():
    """Test MongoDB connection."""
    print("\nTesting MongoDB connection...")
    
    try:
        from Api.Infrastructure.mongodb_connector import MongoDBConnector
        
        connector = MongoDBConnector()
        print(f"   Connection string: {connector.connection_string}")
        
        if connector.connect():
            print("   ✓ MongoDB connection successful")
            connector.disconnect()
            return True
        else:
            print("   ❌ MongoDB connection failed")
            return False
            
    except Exception as e:
        print(f"   ❌ MongoDB connection error: {e}")
        return False

def test_fastapi_app():
    """Test FastAPI app creation."""
    print("\nTesting FastAPI app...")
    
    try:
        from Api.Api.main import app
        print(f"   ✓ FastAPI app created: {app.title}")
        print(f"   ✓ App version: {app.version}")
        return True
        
    except Exception as e:
        print(f"   ❌ FastAPI app error: {e}")
        return False

if __name__ == "__main__":
    print("=== API Debug Test ===\n")
    
    # Test imports
    if not test_imports():
        sys.exit(1)
    
    # Test MongoDB connection
    test_mongodb_connection()
    
    # Test FastAPI app
    if not test_fastapi_app():
        sys.exit(1)
    
    print("\n=== All tests completed ===") 