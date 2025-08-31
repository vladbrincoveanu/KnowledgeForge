"""Pytest configuration and fixtures for E2E tests."""

import os
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Dict, Any
import httpx
import neo4j
import duckdb
from fastapi.testclient import TestClient

# Import the main FastAPI app
import sys
api_path = str(Path(__file__).parent.parent / "api")
sys.path.insert(0, api_path)

# Import the FastAPI app from app.py (not the app package)
import importlib.util
app_spec = importlib.util.spec_from_file_location("app_module", Path(api_path) / "app.py")
app_module = importlib.util.module_from_spec(app_spec)
app_spec.loader.exec_module(app_module)
app = app_module.app
from utils.config import Config


@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """Test configuration with temporary paths and test database settings."""
    return {
        "neo4j": {
            "uri": "bolt://localhost:7687",
            "username": "neo4j", 
            "password": "password",
            "database": "neo4j"  # Use default database for tests
        },
        "metadata_storage": {
            "duckdb_path": ":memory:",  # Use in-memory for tests
        },
        "lmstudio": {
            "base_url": "http://localhost:1234",
            "model_name": "deepseek/deepseek-r1-0528-qwen3-8b",
            "temperature": 0.7,
            "max_tokens": 100,
            "timeout": 30
        },
        "extraction": {
            "confidence_threshold": 0.5,  # Lower threshold for tests
            "batch_size": 100,
            "sample_size": 100
        }
    }


@pytest.fixture(scope="function")
def temp_upload_dir() -> Generator[Path, None, None]:
    """Create temporary directory for file uploads during tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_uploads_"))
    
    # Create uploads subdirectory
    uploads_dir = temp_dir / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    
    # Change working directory to temp dir for the test
    original_cwd = Path.cwd()
    os.chdir(temp_dir)
    
    try:
        yield uploads_dir
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def test_client(temp_upload_dir: Path) -> TestClient:
    """FastAPI test client with temporary upload directory."""
    return TestClient(app)


@pytest.fixture(scope="function")
def http_client() -> Generator[httpx.AsyncClient, None, None]:
    """Async HTTP client for testing the API."""
    with httpx.AsyncClient(base_url="http://testserver") as client:
        yield client


@pytest.fixture(scope="function")
def neo4j_connection(test_config: Dict[str, Any]) -> Generator[neo4j.Driver, None, None]:
    """Neo4j connection for verification."""
    driver = neo4j.GraphDatabase.driver(
        test_config["neo4j"]["uri"],
        auth=(test_config["neo4j"]["username"], test_config["neo4j"]["password"])
    )
    
    # Clean up test database before test
    with driver.session(database=test_config["neo4j"]["database"]) as session:
        session.run("MATCH (n) DETACH DELETE n")
    
    try:
        yield driver
    finally:
        # Clean up test database after test
        with driver.session(database=test_config["neo4j"]["database"]) as session:
            session.run("MATCH (n) DETACH DELETE n")
        driver.close()


@pytest.fixture(scope="function")
def sample_csv_file() -> Path:
    """Path to a sample CSV file for testing."""
    # Use one of the existing sample files
    return Path(__file__).parent.parent / "data" / "sample-data" / "customers.csv"


@pytest.fixture(scope="function")
def small_test_csv(temp_upload_dir: Path) -> Path:
    """Create a small CSV file for testing."""
    csv_content = """id,name,email,city,country
1,John Doe,john@example.com,New York,USA
2,Jane Smith,jane@example.com,London,UK
3,Bob Johnson,bob@example.com,Toronto,Canada
4,Alice Brown,alice@example.com,Sydney,Australia
5,Charlie Wilson,charlie@example.com,Berlin,Germany"""
    
    csv_file = temp_upload_dir / "test_customers.csv"
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture(scope="function", autouse=True)
def setup_test_environment(test_config: Dict[str, Any], monkeypatch):
    """Setup test environment variables."""
    # Override configuration for tests
    monkeypatch.setenv("KF_NEO4J__DATABASE", test_config["neo4j"]["database"])
    monkeypatch.setenv("KF_METADATA_STORAGE__DUCKDB_PATH", test_config["metadata_storage"]["duckdb_path"])
    monkeypatch.setenv("KF_EXTRACTION__CONFIDENCE_THRESHOLD", str(test_config["extraction"]["confidence_threshold"]))
    monkeypatch.setenv("KF_EXTRACTION__BATCH_SIZE", str(test_config["extraction"]["batch_size"]))
    monkeypatch.setenv("KF_EXTRACTION__SAMPLE_SIZE", str(test_config["extraction"]["sample_size"]))
