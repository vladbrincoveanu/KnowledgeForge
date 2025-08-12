#!/usr/bin/env python3
"""
UI Test Runner

Runs all UI tests and provides a comprehensive test report.
"""

import unittest
import sys
import os
import time
import json
from datetime import datetime

# Add the UI src directory to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../UI/src'))

def run_ui_tests():
    """Run all UI tests and return results."""
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Create test runner
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run tests
    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()
    
    return {
        'result': result,
        'duration': end_time - start_time,
        'timestamp': datetime.now().isoformat()
    }

def generate_test_report(test_results):
    """Generate a comprehensive test report."""
    result = test_results['result']
    
    # Calculate statistics
    total_tests = result.testsRun
    failed_tests = len(result.failures)
    errored_tests = len(result.errors)
    skipped_tests = len(result.skipped) if hasattr(result, 'skipped') else 0
    passed_tests = total_tests - failed_tests - errored_tests - skipped_tests
    
    # Calculate success rate
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    # Generate report
    report = {
        'summary': {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'errored_tests': errored_tests,
            'skipped_tests': skipped_tests,
            'success_rate': round(success_rate, 2),
            'duration': round(test_results['duration'], 2),
            'timestamp': test_results['timestamp']
        },
        'failures': [
            {
                'test_name': failure[0]._testMethodName,
                'test_class': failure[0].__class__.__name__,
                'error_message': failure[1]
            }
            for failure in result.failures
        ],
        'errors': [
            {
                'test_name': error[0]._testMethodName,
                'test_class': error[0].__class__.__name__,
                'error_message': error[1]
            }
            for error in result.errors
        ]
    }
    
    return report

def print_test_report(report):
    """Print a formatted test report."""
    print("\n" + "="*60)
    print("UI TEST REPORT")
    print("="*60)
    
    summary = report['summary']
    print(f"\n📊 SUMMARY:")
    print(f"   Total Tests: {summary['total_tests']}")
    print(f"   ✅ Passed: {summary['passed_tests']}")
    print(f"   ❌ Failed: {summary['failed_tests']}")
    print(f"   ⚠️  Errors: {summary['errored_tests']}")
    print(f"   ⏭️  Skipped: {summary['skipped_tests']}")
    print(f"   📈 Success Rate: {summary['success_rate']}%")
    print(f"   ⏱️  Duration: {summary['duration']}s")
    print(f"   🕐 Timestamp: {summary['timestamp']}")
    
    if report['failures']:
        print(f"\n❌ FAILURES ({len(report['failures'])}):")
        for i, failure in enumerate(report['failures'], 1):
            print(f"   {i}. {failure['test_class']}.{failure['test_name']}")
            print(f"      Error: {failure['error_message'].split('AssertionError:')[-1].strip()}")
    
    if report['errors']:
        print(f"\n⚠️  ERRORS ({len(report['errors'])}):")
        for i, error in enumerate(report['errors'], 1):
            print(f"   {i}. {error['test_class']}.{error['test_name']}")
            print(f"      Error: {error['error_message'].split('Exception:')[-1].strip()}")
    
    # Print overall status
    if summary['success_rate'] == 100:
        print(f"\n🎉 ALL TESTS PASSED! ({summary['success_rate']}% success rate)")
    elif summary['success_rate'] >= 80:
        print(f"\n✅ MOST TESTS PASSED ({summary['success_rate']}% success rate)")
    else:
        print(f"\n❌ MANY TESTS FAILED ({summary['success_rate']}% success rate)")
    
    print("="*60)

def save_test_report(report, filename='ui_test_report.json'):
    """Save test report to JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Test report saved to: {filename}")
    except Exception as e:
        print(f"\n⚠️  Could not save test report: {e}")

def run_specific_test_category(category):
    """Run tests for a specific category."""
    categories = {
        'modal': ['TestConnectionPrompt', 'TestModalUI'],
        'integration': ['TestUIIntegration'],
        'responsiveness': ['TestUIResponsiveness'],
        'components': ['TestFileUploader', 'TestGraphComponent', 'TestAppComponent']
    }
    
    if category not in categories:
        print(f"❌ Unknown category: {category}")
        print(f"Available categories: {', '.join(categories.keys())}")
        return
    
    # Load specific test classes
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    for test_class in categories[category]:
        try:
            # Import and add test class
            module = __import__(f'test_ui_components', fromlist=[test_class])
            test_class_obj = getattr(module, test_class)
            tests = loader.loadTestsFromTestCase(test_class_obj)
            suite.addTests(tests)
        except (ImportError, AttributeError):
            try:
                module = __import__(f'test_ui_functionality', fromlist=[test_class])
                test_class_obj = getattr(module, test_class)
                tests = loader.loadTestsFromTestCase(test_class_obj)
                suite.addTests(tests)
            except (ImportError, AttributeError):
                print(f"⚠️  Could not find test class: {test_class}")
    
    if suite.countTestCases() == 0:
        print(f"❌ No tests found for category: {category}")
        return
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()
    
    test_results = {
        'result': result,
        'duration': end_time - start_time,
        'timestamp': datetime.now().isoformat()
    }
    
    report = generate_test_report(test_results)
    print_test_report(report)

def main():
    """Main function to run UI tests."""
    if len(sys.argv) > 1:
        category = sys.argv[1].lower()
        print(f"🧪 Running {category} tests...")
        run_specific_test_category(category)
    else:
        print("🧪 Running all UI tests...")
        test_results = run_ui_tests()
        report = generate_test_report(test_results)
        print_test_report(report)
        
        # Save report
        save_test_report(report)
        
        # Exit with appropriate code
        if report['summary']['success_rate'] == 100:
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == '__main__':
    main() 