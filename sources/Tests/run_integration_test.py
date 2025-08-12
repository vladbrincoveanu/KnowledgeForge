#!/usr/bin/env python3
"""
Integration Test Runner

This script runs the comprehensive integration test for CSV upload and connection detection.
It ensures the API and MongoDB are running before executing the tests.
"""

import os
import sys
import subprocess
import time
import requests
import signal
from pathlib import Path

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

def check_api_health(base_url="http://localhost:8000", max_retries=30, retry_delay=2):
    """Check if the API is healthy and ready."""
    print(f"🔍 Checking API health at {base_url}...")
    
    for attempt in range(max_retries):
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                if health_data.get("status") == "healthy" and health_data.get("mongodb") == "connected":
                    print("✅ API is healthy and MongoDB is connected")
                    return True
                else:
                    print(f"⚠️  API responded but not fully healthy: {health_data}")
            else:
                print(f"⚠️  API responded with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"⚠️  API not ready (attempt {attempt + 1}/{max_retries}): {e}")
        
        if attempt < max_retries - 1:
            print(f"⏳ Waiting {retry_delay} seconds before retry...")
            time.sleep(retry_delay)
    
    print("❌ API health check failed after maximum retries")
    return False

def check_docker_services():
    """Check if Docker services are running."""
    print("🔍 Checking Docker services...")
    
    try:
        # Check if docker-compose is running
        result = subprocess.run(
            ["docker-compose", "ps"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        if result.returncode == 0:
            output = result.stdout
            if "api" in output.lower() and "mongodb" in output.lower():
                print("✅ Docker services appear to be running")
                return True
            else:
                print("⚠️  Docker services may not be fully started")
                return False
        else:
            print("⚠️  Could not check Docker services")
            return False
            
    except FileNotFoundError:
        print("⚠️  docker-compose not found, assuming services are running manually")
        return True
    except Exception as e:
        print(f"⚠️  Error checking Docker services: {e}")
        return False

def start_docker_services():
    """Start Docker services if they're not running."""
    print("🚀 Starting Docker services...")
    
    try:
        # Start services in background
        subprocess.run(
            ["docker-compose", "up", "-d"],
            cwd=Path(__file__).parent.parent,
            check=True
        )
        print("✅ Docker services started")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Docker services: {e}")
        return False
    except FileNotFoundError:
        print("⚠️  docker-compose not found, please start services manually")
        return False

def stop_docker_services():
    """Stop Docker services."""
    print("🛑 Stopping Docker services...")
    
    try:
        subprocess.run(
            ["docker-compose", "down"],
            cwd=Path(__file__).parent.parent,
            check=True
        )
        print("✅ Docker services stopped")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Could not stop Docker services")

def run_integration_test():
    """Run the integration test."""
    print("🧪 Running integration test...")
    
    try:
        # Import and run the integration test
        from integration_test_csv_upload_and_connection import run_integration_test as run_test
        return run_test()
    except ImportError as e:
        print(f"❌ Failed to import integration test: {e}")
        return False
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def main():
    """Main function to run the integration test with proper setup."""
    print("🚀 KnowledgeForge Integration Test Runner")
    print("=" * 50)
    
    # Check if we're in the right directory
    current_dir = Path(__file__).parent
    if not (current_dir / "integration_test_csv_upload_and_connection.py").exists():
        print("❌ Integration test file not found. Please run this script from the Tests directory.")
        sys.exit(1)
    
    # Check Docker services
    if not check_docker_services():
        print("🔄 Attempting to start Docker services...")
        if not start_docker_services():
            print("❌ Could not start Docker services. Please start them manually:")
            print("   cd sources && docker-compose up -d")
            sys.exit(1)
        
        # Wait a bit for services to start
        print("⏳ Waiting for services to start...")
        time.sleep(10)
    
    # Check API health
    if not check_api_health():
        print("❌ API is not healthy. Please ensure:")
        print("   1. Docker services are running: docker-compose up -d")
        print("   2. API is accessible at http://localhost:8000")
        print("   3. MongoDB is connected")
        sys.exit(1)
    
    # Run the integration test
    print("\n" + "=" * 50)
    success = run_integration_test()
    
    # Print final results
    print("\n" + "=" * 50)
    if success:
        print("🎉 Integration test completed successfully!")
        print("✅ All components are working correctly:")
        print("   - CSV file upload and processing")
        print("   - MongoDB data storage (2 nodes)")
        print("   - Connection detection and edge creation (1 edge)")
        print("   - Metadata generation and validation")
        print("   - Visual representation data preparation")
    else:
        print("❌ Integration test failed!")
        print("Please check the test output above for details.")
    
    # Ask if user wants to stop services
    try:
        response = input("\nDo you want to stop Docker services? (y/N): ").strip().lower()
        if response in ['y', 'yes']:
            stop_docker_services()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n🛑 Received interrupt signal, stopping services...")
        stop_docker_services()
        sys.exit(1)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    main() 