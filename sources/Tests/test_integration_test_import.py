#!/usr/bin/env python3
"""
Test to verify the integration test can be imported and has the correct structure.
"""

import unittest
import sys
import os
from pathlib import Path

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

class TestIntegrationTestImport(unittest.TestCase):
    """Test that the integration test can be imported and has correct structure."""
    
    def test_01_import_integration_test(self):
        """Test that the integration test module can be imported."""
        try:
            import integration_test_csv_upload_and_connection
            self.assertTrue(True, "Integration test module imported successfully")
        except ImportError as e:
            self.fail(f"Failed to import integration test module: {e}")
    
    def test_02_test_class_exists(self):
        """Test that the test class exists."""
        try:
            from integration_test_csv_upload_and_connection import TestCSVUploadAndConnectionIntegration
            self.assertTrue(True, "Test class imported successfully")
        except ImportError as e:
            self.fail(f"Failed to import test class: {e}")
    
    def test_03_test_methods_exist(self):
        """Test that all expected test methods exist."""
        from integration_test_csv_upload_and_connection import TestCSVUploadAndConnectionIntegration
        
        expected_methods = [
            'test_01_health_check',
            'test_02_clear_existing_data',
            'test_03_upload_customers_csv',
            'test_04_upload_orders_csv',
            'test_05_verify_collections_in_mongodb',
            'test_06_verify_data_in_collections',
            'test_07_trigger_connection_detection',
            'test_08_create_connection_manually',
            'test_09_confirm_connection_and_create_edge',
            'test_10_verify_edge_in_mongodb',
            'test_11_verify_graph_data_for_visualization',
            'test_12_verify_visual_representation_components',
            'test_13_end_to_end_flow_verification'
        ]
        
        test_instance = TestCSVUploadAndConnectionIntegration()
        
        for method_name in expected_methods:
            self.assertTrue(
                hasattr(test_instance, method_name),
                f"Test method {method_name} not found"
            )
    
    def test_04_test_files_exist(self):
        """Test that the required test files exist."""
        test_files_dir = Path(__file__).parent.parent / "UI" / "sample-data"
        
        customers_csv = test_files_dir / "customers.csv"
        orders_csv = test_files_dir / "orders.csv"
        
        self.assertTrue(customers_csv.exists(), f"Test file not found: {customers_csv}")
        self.assertTrue(orders_csv.exists(), f"Test file not found: {orders_csv}")
    
    def test_05_run_function_exists(self):
        """Test that the run function exists."""
        try:
            from integration_test_csv_upload_and_connection import run_integration_test
            self.assertTrue(callable(run_integration_test), "run_integration_test is callable")
        except ImportError as e:
            self.fail(f"Failed to import run_integration_test function: {e}")


def run_import_test():
    """Run the import test suite."""
    print("🔍 Testing Integration Test Import and Structure")
    print("=" * 50)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestIntegrationTestImport)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 50)
    if result.wasSuccessful():
        print("✅ All import tests passed!")
        print("✅ Integration test structure is correct")
        print("✅ Test files are available")
        print("✅ Ready to run full integration test")
    else:
        print("❌ Some import tests failed!")
        print(f"   - Tests run: {result.testsRun}")
        print(f"   - Failures: {len(result.failures)}")
        print(f"   - Errors: {len(result.errors)}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_import_test()
    sys.exit(0 if success else 1) 