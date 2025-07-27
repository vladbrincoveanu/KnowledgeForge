# CSV Metadata Extractor API

A scalable Python API for extracting comprehensive metadata schema from CSV files. Built with a clean architecture that separates concerns and enables easy extension.

## 🏗️ Architecture

The API follows a clean, modular structure:

```
api/
├── main.py                    # Main entry point and API interface
├── csv_metadata_extractor.py  # Core extraction logic
├── requirements.txt           # Python dependencies
├── README.md                 # This documentation
└── sample_data.csv           # Example data for testing
```

## 🚀 Features

- **Clean Architecture**: Separated concerns with main API interface and core extraction logic
- **Scalable Design**: Easy to extend with new functionality
- **Multiple Processing Modes**: Single file, batch processing, and schema comparison
- **Comprehensive Data Type Detection**: Integer, float, string, datetime, boolean
- **Column Analysis**: Detailed statistics including null counts, unique values, ranges
- **File Metadata**: Size, row count, column count, modification timestamps
- **Schema Summary**: Categorized overview of column types
- **Multiple Encoding Support**: UTF-8, Latin-1, CP1252, ISO-8859-1
- **JSON Output**: Structured metadata in JSON format

## 📦 Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Make scripts executable (optional):**
   ```bash
   chmod +x main.py csv_metadata_extractor.py
   ```

## 🎯 Usage

### Command Line Interface

#### Single File Processing
```bash
# Basic extraction
python main.py data.csv

# With detailed output
python main.py data.csv --pretty

# Save to specific file
python main.py data.csv -o metadata.json
```

#### Multiple File Processing
```bash
# Process multiple files
python main.py file1.csv file2.csv file3.csv

# Process with output directory
python main.py *.csv --output-dir ./metadata

# Compare schemas across files
python main.py file1.csv file2.csv file3.csv --compare
```

#### Schema Comparison
```bash
# Compare schemas and save results
python main.py file1.csv file2.csv --compare --output-dir ./comparison
```

### Programmatic Usage

```python
from main import MetadataExtractionAPI

# Initialize API
api = MetadataExtractionAPI()

# Single file extraction
metadata = api.extract_metadata('data.csv', pretty_print=True)

# Multiple files
results = api.extract_multiple_files(['file1.csv', 'file2.csv'])

# Schema comparison
comparison = api.compare_schemas(['file1.csv', 'file2.csv', 'file3.csv'])
```

### Direct Module Usage

```python
from csv_metadata_extractor import CSVMetadataExtractor

# Create extractor
extractor = CSVMetadataExtractor('data.csv')

# Extract metadata
metadata = extractor.extract_metadata()

# Save metadata
extractor.save_metadata('output.json')
```

## 📊 Output Format

The metadata is structured as follows:

```json
{
  "file_info": {
    "file_name": "example.csv",
    "file_size_mb": 0.5,
    "total_rows": 1000,
    "total_columns": 5,
    "has_duplicates": false,
    "duplicate_rows_count": 0,
    "extraction_timestamp": "2024-01-15T10:30:00"
  },
  "columns": {
    "column_name": {
      "position": 0,
      "total_count": 1000,
      "null_count": 50,
      "null_percentage": 5.0,
      "type": "integer",
      "subtype": "int64",
      "nullable": true,
      "unique_count": 100,
      "min_value": 1,
      "max_value": 1000,
      "sample_values": [1, 2, 3, 4, 5]
    }
  },
  "schema_summary": {
    "numeric_columns_count": 2,
    "categorical_columns_count": 2,
    "datetime_columns_count": 1,
    "boolean_columns_count": 0,
    "numeric_columns": ["age", "salary"],
    "categorical_columns": ["name", "department"],
    "datetime_columns": ["hire_date"],
    "boolean_columns": []
  }
}
```

## 🔧 API Reference

### MetadataExtractionAPI Class

#### Methods

- `extract_metadata(csv_path, output_path=None, pretty_print=False)`: Extract metadata from single file
- `extract_multiple_files(csv_files, output_dir=None, pretty_print=False)`: Process multiple files
- `compare_schemas(csv_files)`: Compare schemas across multiple files

### CSVMetadataExtractor Class

#### Methods

- `extract_metadata()`: Extract comprehensive metadata
- `save_metadata(output_path=None)`: Save metadata to JSON file
- `load_csv()`: Load CSV file with encoding detection

## 🧪 Examples

### Example 1: Basic Single File Processing

```bash
python main.py sample_data.csv --pretty
```

Output:
```
==================================================
CSV METADATA EXTRACTION RESULTS
==================================================

📁 FILE INFORMATION:
   File: sample_data.csv
   Size: 0.00 MB
   Rows: 10
   Columns: 8

📊 SCHEMA SUMMARY:
   Numeric columns: 3
   Categorical columns: 3
   Datetime columns: 1
   Boolean columns: 1

📋 COLUMN DETAILS:

   🔹 id:
      Type: integer (int64)
      Nullable: false
      Null count: 0 (0.0%)
      Unique values: 10
      Range: 1 to 10
      Sample values: [1, 2, 3]
```

### Example 2: Schema Comparison

```bash
python main.py file1.csv file2.csv --compare
```

Output:
```
==================================================
SCHEMA COMPARISON RESULTS
==================================================

📊 Files analyzed: 2/2
🔗 Common columns: 3
🔍 Unique columns: 2

📋 Common columns: id, name, age
```

### Example 3: Programmatic Integration

```python
from main import MetadataExtractionAPI

# Initialize API
api = MetadataExtractionAPI()

# Process multiple files
files = ['data1.csv', 'data2.csv', 'data3.csv']
results = api.extract_multiple_files(files, output_dir='./metadata')

# Compare schemas
comparison = api.compare_schemas(files)
print(f"Common columns: {comparison['common_columns']}")
```

## 🔄 Extending the API

The clean architecture makes it easy to extend functionality:

### Adding New Data Types

```python
# In csv_metadata_extractor.py
def infer_data_type(self, column):
    # Add your custom data type detection logic
    if self._is_custom_type(column):
        return {
            "type": "custom",
            "subtype": "custom_type",
            # ... other properties
        }
    # ... existing logic
```

### Adding New Processing Modes

```python
# In main.py
class MetadataExtractionAPI:
    def new_processing_mode(self, csv_files):
        # Add your custom processing logic
        pass
```

## 🛠️ Error Handling

The API handles various error scenarios:

- **File not found**: Clear error messages with file paths
- **Encoding issues**: Automatic encoding detection and fallback
- **Corrupted data**: Graceful handling of malformed CSV data
- **Memory issues**: Efficient processing for large files

## 📈 Performance

- **Small files** (< 1MB): Near-instant processing
- **Medium files** (1-100MB): Seconds to minutes
- **Large files** (> 100MB): May take several minutes depending on system

## 🤝 Contributing

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes following the clean architecture
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is part of the KnowledgeForge platform and follows the same licensing terms. 