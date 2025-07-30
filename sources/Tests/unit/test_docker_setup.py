"""
Docker Infrastructure Test Script

This script tests the Docker infrastructure setup and connectivity.
"""

import requests
import time
import subprocess
import sys
import os

def test_service_health(url, service_name, timeout=30):
    """Test if a service is responding."""
    print(f"🔍 Testing {service_name} at {url}")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {service_name} is healthy")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
    
    print(f"❌ {service_name} is not responding")
    return False

def test_mongodb_connection():
    """Test MongoDB connection."""
    print("🔍 Testing MongoDB connection")
    
    try:
        # Try to connect to MongoDB using docker exec
        result = subprocess.run([
            "docker", "exec", "knowlly-mongodb", 
            "mongosh", "--eval", "db.adminCommand('ping')"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ MongoDB is accessible")
            return True
        else:
            print(f"❌ MongoDB connection failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ MongoDB connection timeout")
        return False
    except FileNotFoundError:
        print("❌ Docker not found or not running")
        return False

def test_redis_connection():
    """Test Redis connection."""
    print("🔍 Testing Redis connection")
    
    try:
        result = subprocess.run([
            "docker", "exec", "knowlly-redis", 
            "redis-cli", "ping"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "PONG" in result.stdout:
            print("✅ Redis is accessible")
            return True
        else:
            print(f"❌ Redis connection failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Redis connection timeout")
        return False
    except FileNotFoundError:
        print("❌ Docker not found or not running")
        return False

def test_minio_connection():
    """Test MinIO connection."""
    print("🔍 Testing MinIO connection")
    
    try:
        result = subprocess.run([
            "docker", "exec", "knowlly-minio", 
            "curl", "-f", "http://localhost:9000/minio/health/live"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ MinIO is accessible")
            return True
        else:
            print(f"❌ MinIO connection failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ MinIO connection timeout")
        return False
    except FileNotFoundError:
        print("❌ Docker not found or not running")
        return False

def check_docker_services():
    """Check if Docker services are running."""
    print("🔍 Checking Docker services")
    
    try:
        result = subprocess.run([
            "docker-compose", "ps"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Docker Compose services:")
            print(result.stdout)
            return True
        else:
            print(f"❌ Docker Compose check failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Docker Compose check timeout")
        return False
    except FileNotFoundError:
        print("❌ Docker Compose not found")
        return False

def main():
    """Main test function."""
    
    print("🚀 Docker Infrastructure Test")
    print("=" * 50)
    
    # Check if Docker services are running
    if not check_docker_services():
        print("\n❌ Docker services are not running.")
        print("Please start the services with: docker-compose up -d")
        return False
    
    print("\n" + "=" * 50)
    print("Testing Service Connectivity")
    print("=" * 50)
    
    # Test service health endpoints
    services = [
        ("http://localhost:8000/health", "API"),
        ("http://localhost:8081", "MongoDB Express"),
        ("http://localhost:9001", "MinIO Console"),
    ]
    
    health_results = []
    for url, service_name in services:
        health_results.append(test_service_health(url, service_name))
    
    print("\n" + "=" * 50)
    print("Testing Database Connectivity")
    print("=" * 50)
    
    # Test database connections
    db_results = []
    db_results.append(test_mongodb_connection())
    db_results.append(test_redis_connection())
    db_results.append(test_minio_connection())
    
    print("\n" + "=" * 50)
    print("Test Results Summary")
    print("=" * 50)
    
    # Calculate results
    total_tests = len(health_results) + len(db_results)
    passed_tests = sum(health_results) + sum(db_results)
    
    print(f"📊 Health Checks: {sum(health_results)}/{len(health_results)} passed")
    print(f"📊 Database Tests: {sum(db_results)}/{len(db_results)} passed")
    print(f"📊 Overall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed! Docker infrastructure is working correctly.")
        print("\n📋 Service URLs:")
        print("  - API: http://localhost:8000")
        print("  - API Docs: http://localhost:8000/docs")
        print("  - MongoDB Express: http://localhost:8081")
        print("  - MinIO Console: http://localhost:9001")
        print("  - Redis Commander: http://localhost:8082")
        print("  - Portainer: http://localhost:9002")
        return True
    else:
        print("\n⚠️  Some tests failed. Please check the service logs:")
        print("  docker-compose logs")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 