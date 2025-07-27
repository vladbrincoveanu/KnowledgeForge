#!/usr/bin/env python3
"""
Test runner for CSV Metadata Extractor API.

Runs all unit tests and provides comprehensive test results.
"""

import unittest
import sys
import os
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_all_tests():
    """Run all test suites."""
    print("🧪 CSV Metadata Extractor API - Test Suite")
    print("=" * 60)
    
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__), 'tests')
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.failures:
        print("\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n🚨 ERRORS:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    # Overall result
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        return True
    else:
        print("\n❌ Some tests failed!")
        return False


def run_specific_test(test_file):
    """Run a specific test file."""
    print(f"🧪 Running specific test: {test_file}")
    print("=" * 60)
    
    # Import and run specific test
    test_path = os.path.join(os.path.dirname(__file__), 'tests', test_file)
    
    if not os.path.exists(test_path):
        print(f"❌ Test file not found: {test_path}")
        return False
    
    # Add tests directory to path
    tests_dir = os.path.join(os.path.dirname(__file__), 'tests')
    sys.path.insert(0, tests_dir)
    
    # Import and run the specific test
    module_name = test_file.replace('.py', '')
    try:
        module = __import__(module_name)
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        return result.wasSuccessful()
    except ImportError as e:
        print(f"❌ Error importing test module: {e}")
        return False


def run_demo_tests():
    """Run demo tests with sample data."""
    print("🎯 Running Demo Tests with Sample Data")
    print("=" * 60)
    
    try:
        from main import MetadataExtractionAPI
        
        api = MetadataExtractionAPI()
        
        # Test with sample data files
        sample_files = [
            'sample_data/employees.csv',
            'sample_data/products.csv',
            'sample_data/sales.csv',
            'sample_data/customers.csv',
            'sample_data/inventory.csv'
        ]
        
        successful_tests = 0
        total_tests = len(sample_files)
        
        for file_path in sample_files:
            if os.path.exists(file_path):
                try:
                    print(f"\n📁 Testing: {file_path}")
                    metadata = api.extract_metadata(file_path)
                    
                    # Basic validation
                    if 'file_info' in metadata and 'columns' in metadata:
                        print(f"   ✅ Success: {metadata['file_info']['total_rows']} rows, {metadata['file_info']['total_columns']} columns")
                        successful_tests += 1
                    else:
                        print(f"   ❌ Failed: Invalid metadata structure")
                        
                except Exception as e:
                    print(f"   ❌ Error: {e}")
            else:
                print(f"   ⚠️  File not found: {file_path}")
        
        print(f"\n📊 Demo Test Results: {successful_tests}/{total_tests} successful")
        return successful_tests == total_tests
        
    except Exception as e:
        print(f"❌ Demo test error: {e}")
        return False


def main():
    """Main test runner function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run CSV Metadata Extractor API tests")
    parser.add_argument('--specific', help='Run a specific test file (e.g., test_csv_metadata_extractor.py)')
    parser.add_argument('--demo', action='store_true', help='Run demo tests with sample data')
    parser.add_argument('--all', action='store_true', help='Run all tests (default)')
    
    args = parser.parse_args()
    
    if args.specific:
        success = run_specific_test(args.specific)
    elif args.demo:
        success = run_demo_tests()
    else:
        # Default: run all tests
        success = run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main() 