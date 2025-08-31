# End-to-End Tests for KnowledgeForge

This directory contains comprehensive end-to-end tests for the KnowledgeForge CSV upload and processing pipeline.

## Overview

The E2E tests validate the complete workflow:

1. **File Upload** - CSV file upload through FastAPI endpoints
2. **Metadata Storage** - File metadata persistence in DuckDB
3. **Entity Extraction** - LLM-powered entity extraction from CSV data
4. **Ontology Mapping** - Mapping extracted entities to standard ontologies
5. **Relationship Discovery** - Finding relationships between entities
6. **Graph Storage** - Persisting entities and relationships in Neo4j
7. **API Integration** - Full API workflow validation

## Test Structure

```
e2e/
├── conftest.py                    # Pytest fixtures and configuration
├── test_helpers.py               # Helper classes for testing
├── test_csv_upload_pipeline.py   # Main E2E test suite
├── requirements.txt              # Testing dependencies
├── pytest.ini                   # Pytest configuration
└── README.md                    # This file
```

## Prerequisites

### 1. Services Running

Ensure the following services are running before executing tests:

- **Neo4j**: `bolt://localhost:7687` (with test database)
- **LM Studio**: `http://localhost:1234` (with required models)
- **FastAPI Backend**: The main API service

### 2. Test Database

Create a separate Neo4j database for testing:

```cypher
CREATE DATABASE test_knowledge_forge;
```

### 3. Environment Setup

Install test dependencies:

```bash
cd sources/e2e
pip install -r requirements.txt
```

## Running Tests

### Basic Test Execution

```bash
# Run all E2E tests
pytest

# Run with verbose output
pytest -v

# Run specific test
pytest test_csv_upload_pipeline.py::TestCSVUploadPipeline::test_complete_csv_upload_pipeline
```

### Advanced Options

```bash
# Run tests with coverage
pytest --cov=../api

# Run tests in parallel (if multiple test files)
pytest -n auto

# Run only fast tests (skip slow integration tests)
pytest -m "not slow"

# Run with detailed logging
pytest --log-cli-level=DEBUG

# Stop on first failure
pytest -x
```

## Test Configuration

### Environment Variables

Override test configuration using environment variables:

```bash
export KF_NEO4J__DATABASE=test_knowledge_forge
export KF_NEO4J__URI=bolt://localhost:7687
export KF_LMSTUDIO__BASE_URL=http://localhost:1234
export KF_EXTRACTION__CONFIDENCE_THRESHOLD=0.5
```

### Custom Configuration

Tests use a test-specific configuration that:
- Uses in-memory DuckDB for metadata storage
- Connects to test Neo4j database
- Uses lower confidence thresholds for entity extraction
- Processes smaller data samples for faster execution

## Test Cases

### 1. Complete Pipeline Test (`test_complete_csv_upload_pipeline`)

**Purpose**: Validates the entire CSV upload and processing workflow

**Steps**:
1. Validates test CSV structure
2. Uploads CSV file via API
3. Verifies file storage and metadata
4. Starts extraction process
5. Monitors extraction progress
6. Validates Neo4j node creation
7. Checks entity and relationship extraction
8. Verifies data integrity

**Expected Results**:
- File uploaded successfully
- Extraction completes without errors
- Neo4j contains expected nodes and relationships
- Extracted entities match CSV data

### 2. Error Handling Test (`test_csv_upload_error_handling`)

**Purpose**: Validates proper error handling

**Test Cases**:
- Non-CSV file upload (should be rejected)
- Empty file upload (should be rejected)
- Missing file parameter (should return 422)

### 3. Complex Data Test (`test_extraction_with_different_csv_formats`)

**Purpose**: Tests pipeline with various data types

**Features**:
- Multiple column types (strings, numbers, dates, booleans)
- Different data formats
- Complex entity extraction scenarios

### 4. Concurrent Upload Test (`test_concurrent_uploads`)

**Purpose**: Validates system behavior under concurrent load

**Features**:
- Multiple simultaneous file uploads
- Concurrent extraction processing
- Resource contention handling

## Test Data

Tests use both:
- **Generated Test Data**: Small CSV files created in fixtures
- **Sample Data**: Existing files from `sources/data/sample-data/`

### Sample Test CSV

```csv
id,name,email,city,country
1,John Doe,john@example.com,New York,USA
2,Jane Smith,jane@example.com,London,UK
3,Bob Johnson,bob@example.com,Toronto,Canada
```

## Debugging Tests

### View Test Logs

```bash
# Run with full logging
pytest --log-cli-level=DEBUG -s

# Capture stdout/stderr
pytest -s
```

### Debug Specific Failures

```bash
# Drop into debugger on failure
pytest --pdb

# Run only failed tests from last run
pytest --lf
```

### Neo4j Debugging

```cypher
-- Connect to test database
USE test_knowledge_forge;

-- View all nodes
MATCH (n) RETURN n LIMIT 10;

-- Count nodes by type
MATCH (n) RETURN labels(n) as type, count(n) as count;

-- Clear test data
MATCH (n) DETACH DELETE n;
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    services:
      neo4j:
        image: neo4j:5.15
        env:
          NEO4J_AUTH: neo4j/password
        ports:
          - 7687:7687
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd sources/e2e
          pip install -r requirements.txt
      
      - name: Run E2E tests
        run: |
          cd sources/e2e
          pytest --tb=short
```

## Performance Expectations

- **Single Test Runtime**: 30-120 seconds
- **Full Suite Runtime**: 5-10 minutes
- **Memory Usage**: ~500MB (including Neo4j test data)
- **Network**: Requires local service connections

## Troubleshooting

### Common Issues

1. **Neo4j Connection Failed**
   - Verify Neo4j is running: `docker ps` or service status
   - Check test database exists: `SHOW DATABASES;`
   - Verify credentials in test configuration

2. **LM Studio Not Available**
   - Start LM Studio service
   - Verify model is loaded
   - Check base URL configuration

3. **File Upload Fails**
   - Check file permissions
   - Verify uploads directory is writable
   - Check available disk space

4. **Slow Test Execution**
   - Reduce sample sizes in test configuration
   - Use smaller test CSV files
   - Check system resources

### Debug Commands

```bash
# Check service connectivity
curl http://localhost:1234/v1/models
neo4j-admin database info test_knowledge_forge

# View detailed test output
pytest -vvv --tb=long

# Run single test for debugging
pytest test_csv_upload_pipeline.py::TestCSVUploadPipeline::test_complete_csv_upload_pipeline -s
```

## Contributing

When adding new E2E tests:

1. Follow the existing test structure
2. Use the provided test helpers
3. Add appropriate error handling tests
4. Include performance considerations
5. Update this README with new test descriptions

## Related Documentation

- [API Documentation](../api/docs/)
- [Entity Extraction](../api/docs/ENTITY_EXTRACTOR.md)
- [Ontology Mapping](../api/docs/ONTOLOGY_MAPPER.md)
- [Configuration Guide](../api/docs/CONFIGURATION.md)
