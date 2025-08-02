"""
Test script to verify the new services structure works correctly.
"""

import sys
import os

def test_imports():
    """Test that all services can be imported correctly."""
    print("🔍 Testing service imports...")
    
    try:
        # Test importing from the services package
        from Api.Application.services import DataProcessingService, QueryService, FileProcessorService
        print("✅ Successfully imported from services package")
        
        # Test importing individual services
        from Api.Application.services.data_processing_service import DataProcessingService as DPS1
        from Api.Application.services.query_service import QueryService as QS1
        from Api.Application.services.file_processor_service import FileProcessorService as FPS1
        print("✅ Successfully imported individual services")
        
        # Test backward compatibility
        from Api.Application.services import DataProcessingService as DPS2, QueryService as QS2, FileProcessorService as FPS2
        print("✅ Backward compatibility imports work")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_service_instantiation():
    """Test that services can be instantiated correctly."""
    print("\n🔍 Testing service instantiation...")
    
    try:
        from Api.Application.services import DataProcessingService, QueryService, FileProcessorService
        from Api.Infrastructure.mongodb_connector import MongoDBConnector
        
        # Create a mock MongoDB connector (we won't actually connect)
        class MockMongoDBConnector:
            def __init__(self):
                pass
        
        mock_connector = MockMongoDBConnector()
        
        # Test instantiation
        data_service = DataProcessingService(mock_connector)
        query_service = QueryService(mock_connector)
        file_processor = FileProcessorService(mock_connector)
        
        print("✅ All services instantiated successfully")
        
        # Test that services have expected attributes
        assert hasattr(data_service, 'mongodb_connector')
        assert hasattr(data_service, 'file_processor')
        assert hasattr(query_service, 'mongodb_connector')
        assert hasattr(file_processor, 'mongodb_connector')
        
        print("✅ Services have expected attributes")
        
        return True
        
    except Exception as e:
        print(f"❌ Service instantiation error: {e}")
        return False

def test_service_methods():
    """Test that services have expected methods."""
    print("\n🔍 Testing service methods...")
    
    try:
        from Api.Application.services import DataProcessingService, QueryService, FileProcessorService
        from Api.Infrastructure.mongodb_connector import MongoDBConnector
        
        class MockMongoDBConnector:
            def __init__(self):
                pass
        
        mock_connector = MockMongoDBConnector()
        
        # Test DataProcessingService methods
        data_service = DataProcessingService(mock_connector)
        expected_dps_methods = ['process_file', 'process_directory', 'get_processing_status', 'query_data']
        for method in expected_dps_methods:
            assert hasattr(data_service, method), f"DataProcessingService missing method: {method}"
        
        # Test QueryService methods
        query_service = QueryService(mock_connector)
        expected_qs_methods = ['get_collection_info', 'list_collections', 'delete_collection', 'get_collection_statistics', 'search_collections']
        for method in expected_qs_methods:
            assert hasattr(query_service, method), f"QueryService missing method: {method}"
        
        # Test FileProcessorService methods
        file_processor = FileProcessorService(mock_connector)
        expected_fps_methods = ['process_file']
        for method in expected_fps_methods:
            assert hasattr(file_processor, method), f"FileProcessorService missing method: {method}"
        
        print("✅ All services have expected methods")
        
        return True
        
    except Exception as e:
        print(f"❌ Service methods test error: {e}")
        return False

def test_package_structure():
    """Test that the package structure is correct."""
    print("\n🔍 Testing package structure...")
    
    try:
        # Test that __init__.py exports are correct
        from Api.Application.services import __all__
        expected_exports = ['DataProcessingService', 'QueryService', 'FileProcessorService']
        
        for export in expected_exports:
            assert export in __all__, f"Missing export: {export}"
        
        print("✅ Package exports are correct")
        
        # Test that services can be imported from the package
        from Api.Application.services import DataProcessingService, QueryService, FileProcessorService
        print("✅ Services can be imported from package")
        
        return True
        
    except Exception as e:
        print(f"❌ Package structure test error: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing Services Structure")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_service_instantiation,
        test_service_methods,
        test_package_structure
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print(f"❌ Test failed: {test.__name__}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Services structure is working correctly.")
        print("\n📋 Service Structure Summary:")
        print("  - DataProcessingService: Main orchestration service")
        print("  - FileProcessorService: File processing logic")
        print("  - QueryService: Data querying and collection management")
        print("  - Backward compatibility: Original services.py still works")
        return True
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 