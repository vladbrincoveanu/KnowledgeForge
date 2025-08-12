# Integration Test: CSV Upload and Connection Detection

This integration test verifies the complete end-to-end flow of the KnowledgeForge system, from uploading CSV files to creating visual connections between datasets.

## What the Test Covers

The integration test performs the following comprehensive verification:

### 1. File Upload and Processing
- ✅ Uploads `customers.csv` and `orders.csv` sample files
- ✅ Verifies files are processed correctly by the API
- ✅ Validates metadata extraction and schema detection
- ✅ Confirms data is stored in MongoDB collections

### 2. MongoDB Data Storage (2 Nodes)
- ✅ Verifies exactly 2 collections are created in MongoDB
- ✅ Validates collection metadata and document counts
- ✅ Confirms data integrity and relationships
- ✅ Tests data querying functionality

### 3. Connection Detection and Edge Creation (1 Edge)
- ✅ Triggers connection detection between collections
- ✅ Creates a potential connection manually (since backend detection is disabled)
- ✅ Confirms the connection to create an active edge
- ✅ Validates edge properties and metadata

### 4. Metadata Validation
- ✅ Ensures edge has minimum required metadata
- ✅ Verifies merged metadata structure
- ✅ Validates data quality metrics
- ✅ Confirms connection strength and type

### 5. Visual Representation
- ✅ Tests graph data structure for visualization
- ✅ Verifies compatibility with React components
- ✅ Validates node and link data formats
- ✅ Ensures visual connection is properly represented

## Test Files Used

The test uses the sample CSV files located in `sources/UI/sample-data/`:

- **customers.csv**: Contains customer information (5 rows)
  - Columns: customer_id, customer_name, email, phone, city, country
- **orders.csv**: Contains order information (5 rows)
  - Columns: order_id, customer_id, order_date, product_name, quantity, price, total_amount

## Expected Results

After running the test, you should have:

1. **2 MongoDB Collections (Nodes)**:
   - `customers.csv` collection with 5 documents
   - `orders.csv` collection with 5 documents

2. **1 Edge Connection**:
   - Source: `customers.csv`
   - Target: `orders.csv`
   - Connection column: `customer_id`
   - Type: `foreign_key`
   - Confidence: ≥ 0.7
   - Status: `active`

3. **Complete Metadata**:
   - Total columns in merged dataset
   - Shared columns (minimum 1)
   - Connection strength
   - Merge strategy
   - Data quality metrics
   - Merge complexity

## Running the Test

### Prerequisites

1. **Docker and Docker Compose** installed
2. **Python 3.8+** with required packages
3. **KnowledgeForge project** set up

### Quick Start

1. **Navigate to the Tests directory**:
   ```bash
   cd sources/Tests
   ```

2. **Run the integration test**:
   ```bash
   python run_integration_test.py
   ```

   Or use the executable:
   ```bash
   ./run_integration_test.py
   ```

### Manual Setup (if needed)

If you prefer to run services manually:

1. **Start Docker services**:
   ```bash
   cd sources
   docker-compose up -d
   ```

2. **Wait for services to be ready** (check with `docker-compose ps`)

3. **Run the test**:
   ```bash
   cd Tests
   python integration_test_csv_upload_and_connection.py
   ```

## Test Output

The test provides detailed output showing:

- ✅ Health checks and service status
- ✅ File upload progress and validation
- ✅ MongoDB collection verification
- ✅ Connection detection and edge creation
- ✅ Metadata validation
- ✅ Visual representation testing
- ✅ Final summary with statistics

### Example Output

```
🚀 Starting CSV Upload and Connection Detection Integration Test
======================================================================
✅ API health check passed
✅ Existing data cleared successfully
✅ Customers CSV uploaded successfully: 5 rows inserted
✅ Orders CSV uploaded successfully: 5 rows inserted
✅ MongoDB collections verified: 2 nodes created
✅ Collection data verified with correct customer_id relationships
✅ Connection detection triggered (backend disabled, using frontend system)
✅ Potential connection created manually
✅ Connection confirmed and edge created with metadata
✅ Edge verified in MongoDB with minimum metadata requirements
✅ Graph data verified for visualization
✅ Visual representation components verified
✅ End-to-end flow verification completed successfully
   - 2 nodes (collections) created: ['customers.csv', 'orders.csv']
   - 1 edge created: customers.csv ↔ orders.csv
   - Connection column: customer_id
   - Connection type: foreign_key
   - Confidence score: 0.95
   - Total columns in merged metadata: 12
   - Shared columns: 1

✅ All integration tests passed!
🎉 Complete end-to-end flow verified:
   - CSV files uploaded successfully
   - Data stored in MongoDB (2 nodes)
   - Connection detected and edge created (1 edge)
   - Edge has minimum required metadata
   - Visual representation data prepared
```

## Troubleshooting

### Common Issues

1. **API not accessible**:
   - Ensure Docker services are running: `docker-compose up -d`
   - Check API health: `curl http://localhost:8000/health`

2. **MongoDB connection failed**:
   - Verify MongoDB container is running: `docker-compose ps`
   - Check MongoDB logs: `docker-compose logs mongodb`

3. **Test files not found**:
   - Ensure you're running from the `sources/Tests` directory
   - Verify sample CSV files exist in `sources/UI/sample-data/`

4. **Import errors**:
   - Install required Python packages: `pip install requests pymongo`
   - Ensure Python path includes the API directory

### Debug Mode

For detailed debugging, you can run individual test methods:

```python
# Run specific test
python -m unittest integration_test_csv_upload_and_connection.TestCSVUploadAndConnectionIntegration.test_03_upload_customers_csv
```

## Test Architecture

The integration test follows a systematic approach:

1. **Setup Phase**: Health checks and data cleanup
2. **Upload Phase**: File processing and validation
3. **Storage Phase**: MongoDB verification
4. **Connection Phase**: Edge creation and validation
5. **Visualization Phase**: Graph data preparation
6. **Verification Phase**: End-to-end flow validation

This ensures comprehensive testing of all system components and their interactions.

## Contributing

When adding new features to the system, ensure they pass this integration test. The test serves as a regression test to verify that core functionality remains intact.

To extend the test:

1. Add new test methods to the `TestCSVUploadAndConnectionIntegration` class
2. Follow the naming convention: `test_XX_description`
3. Include proper assertions and error handling
4. Update this README with new test coverage 