#!/usr/bin/env python3
"""
Unit tests for CSV Metadata Extractor.

Tests the core functionality of the CSVMetadataExtractor class.
"""

import unittest
import tempfile
import os
import json
import pandas as pd
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from csv_metadata_extractor import CSVMetadataExtractor


class TestCSVMetadataExtractor(unittest.TestCase):
    """Test cases for CSVMetadataExtractor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test CSV files
        self.create_test_files()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def create_test_files(self):
        """Create various test CSV files."""
        
        # Test file 1: Mixed data types
        self.test_file_1 = os.path.join(self.temp_dir, "test_1.csv")
        with open(self.test_file_1, 'w') as f:
            f.write("id,name,age,salary,department,hire_date,is_active,rating\n")
            f.write("1,John Doe,30,75000.50,Engineering,2023-01-15,true,4.5\n")
            f.write("2,Jane Smith,28,82000.75,Marketing,2023-02-20,true,4.8\n")
            f.write("3,Bob Johnson,35,95000.25,Engineering,2022-11-10,false,3.9\n")
        
        # Test file 2: All numeric
        self.test_file_2 = os.path.join(self.temp_dir, "test_2.csv")
        with open(self.test_file_2, 'w') as f:
            f.write("id,value,score,price\n")
            f.write("1,100,85.5,29.99\n")
            f.write("2,200,92.3,45.50\n")
            f.write("3,300,78.9,12.75\n")
        
        # Test file 3: All strings
        self.test_file_3 = os.path.join(self.temp_dir, "test_3.csv")
        with open(self.test_file_3, 'w') as f:
            f.write("name,city,country,description\n")
            f.write("John Doe,New York,USA,Software Engineer\n")
            f.write("Jane Smith,London,UK,Data Scientist\n")
            f.write("Bob Johnson,Paris,France,Product Manager\n")
        
        # Test file 4: With null values
        self.test_file_4 = os.path.join(self.temp_dir, "test_4.csv")
        with open(self.test_file_4, 'w') as f:
            f.write("id,name,age,salary,department\n")
            f.write("1,John Doe,30,75000.50,Engineering\n")
            f.write("2,,28,,Marketing\n")
            f.write("3,Bob Johnson,,95000.25,\n")
        
        # Test file 5: All null values
        self.test_file_5 = os.path.join(self.temp_dir, "test_5.csv")
        with open(self.test_file_5, 'w') as f:
            f.write("col1,col2,col3\n")
            f.write(",,,\n")
            f.write(",,,\n")
            f.write(",,,\n")
    
    def test_extractor_initialization(self):
        """Test extractor initialization."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        self.assertEqual(extractor.csv_path, self.test_file_1)
        self.assertIsNone(extractor.df)
        self.assertEqual(extractor.metadata, {})
    
    def test_load_csv_success(self):
        """Test successful CSV loading."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        success = extractor.load_csv()
        
        self.assertTrue(success)
        self.assertIsNotNone(extractor.df)
        self.assertEqual(len(extractor.df), 3)  # 3 data rows
        self.assertEqual(len(extractor.df.columns), 8)  # 8 columns
    
    def test_load_csv_file_not_found(self):
        """Test CSV loading with non-existent file."""
        extractor = CSVMetadataExtractor("non_existent_file.csv")
        success = extractor.load_csv()
        
        self.assertFalse(success)
    
    def test_infer_data_type_integer(self):
        """Test integer data type inference."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        extractor.load_csv()
        
        # Test id column (integer)
        id_column = extractor.df['id']
        type_info = extractor.infer_data_type(id_column)
        
        self.assertEqual(type_info['type'], 'integer')
        self.assertEqual(type_info['subtype'], 'int64')
        self.assertFalse(type_info['nullable'])
        self.assertEqual(type_info['unique_count'], 3)
        self.assertEqual(type_info['min_value'], 1)
        self.assertEqual(type_info['max_value'], 3)
    
    def test_infer_data_type_float(self):
        """Test float data type inference."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        extractor.load_csv()
        
        # Test salary column (float)
        salary_column = extractor.df['salary']
        type_info = extractor.infer_data_type(salary_column)
        
        self.assertEqual(type_info['type'], 'float')
        self.assertEqual(type_info['subtype'], 'float64')
        self.assertFalse(type_info['nullable'])
        self.assertEqual(type_info['unique_count'], 3)
        self.assertIsInstance(type_info['min_value'], float)
        self.assertIsInstance(type_info['max_value'], float)
    
    def test_infer_data_type_string(self):
        """Test string data type inference."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        extractor.load_csv()
        
        # Test name column (string)
        name_column = extractor.df['name']
        type_info = extractor.infer_data_type(name_column)
        
        self.assertEqual(type_info['type'], 'string')
        self.assertEqual(type_info['subtype'], 'object')
        self.assertFalse(type_info['nullable'])
        self.assertEqual(type_info['unique_count'], 3)
        self.assertIn('max_length', type_info)
        self.assertIsInstance(type_info['sample_values'], list)
    
    def test_infer_data_type_datetime(self):
        """Test datetime data type inference."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        extractor.load_csv()
        
        # Test hire_date column (datetime)
        date_column = extractor.df['hire_date']
        type_info = extractor.infer_data_type(date_column)
        
        self.assertEqual(type_info['type'], 'datetime')
        self.assertEqual(type_info['subtype'], 'datetime64[ns]')
        self.assertFalse(type_info['nullable'])
        self.assertEqual(type_info['unique_count'], 3)
    
    def test_infer_data_type_boolean(self):
        """Test boolean data type inference."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        extractor.load_csv()
        
        # Test is_active column (boolean)
        bool_column = extractor.df['is_active']
        type_info = extractor.infer_data_type(bool_column)
        
        self.assertEqual(type_info['type'], 'boolean')
        self.assertEqual(type_info['subtype'], 'bool')
        self.assertFalse(type_info['nullable'])
        self.assertEqual(type_info['unique_count'], 2)  # true and false
    
    def test_infer_data_type_with_nulls(self):
        """Test data type inference with null values."""
        extractor = CSVMetadataExtractor(self.test_file_4)
        extractor.load_csv()
        
        # Test name column with nulls
        name_column = extractor.df['name']
        type_info = extractor.infer_data_type(name_column)
        
        self.assertEqual(type_info['type'], 'string')
        self.assertTrue(type_info['nullable'])
        # Note: null_count is calculated in extract_column_metadata, not infer_data_type
    
    def test_infer_data_type_all_nulls(self):
        """Test data type inference with all null values."""
        extractor = CSVMetadataExtractor(self.test_file_5)
        extractor.load_csv()
        
        # Test any column (all nulls)
        col_column = extractor.df['col1']
        type_info = extractor.infer_data_type(col_column)
        
        self.assertEqual(type_info['type'], 'unknown')
        self.assertEqual(type_info['subtype'], 'all_null')
        self.assertTrue(type_info['nullable'])
        self.assertEqual(type_info['unique_count'], 0)
    
    def test_extract_column_metadata(self):
        """Test column metadata extraction."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        extractor.load_csv()
        
        columns_metadata = extractor.extract_column_metadata()
        
        self.assertIsInstance(columns_metadata, dict)
        self.assertEqual(len(columns_metadata), 8)  # 8 columns
        
        # Check specific column metadata
        id_metadata = columns_metadata['id']
        self.assertEqual(id_metadata['position'], 0)
        self.assertEqual(id_metadata['total_count'], 3)
        self.assertEqual(id_metadata['null_count'], 0)
        self.assertEqual(id_metadata['type'], 'integer')
    
    def test_extract_file_metadata(self):
        """Test file metadata extraction."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        extractor.load_csv()
        
        file_metadata = extractor.extract_file_metadata()
        
        self.assertIsInstance(file_metadata, dict)
        self.assertEqual(file_metadata['file_name'], 'test_1.csv')
        self.assertEqual(file_metadata['total_rows'], 3)
        self.assertEqual(file_metadata['total_columns'], 8)
        self.assertIn('file_size_bytes', file_metadata)
        self.assertIn('extraction_timestamp', file_metadata)
    
    def test_extract_schema_summary(self):
        """Test schema summary extraction."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        extractor.load_csv()
        
        # Need to extract metadata first to populate self.metadata
        extractor.extract_metadata()
        
        schema_summary = extractor.extract_schema_summary()
        
        self.assertIsInstance(schema_summary, dict)
        self.assertIn('numeric_columns_count', schema_summary)
        self.assertIn('categorical_columns_count', schema_summary)
        self.assertIn('datetime_columns_count', schema_summary)
        self.assertIn('boolean_columns_count', schema_summary)
        self.assertIn('numeric_columns', schema_summary)
        self.assertIn('categorical_columns', schema_summary)
        self.assertIn('datetime_columns', schema_summary)
        self.assertIn('boolean_columns', schema_summary)
    
    def test_extract_metadata_complete(self):
        """Test complete metadata extraction."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        metadata = extractor.extract_metadata()
        
        self.assertIsInstance(metadata, dict)
        self.assertIn('file_info', metadata)
        self.assertIn('columns', metadata)
        self.assertIn('schema_summary', metadata)
        
        # Check file info
        self.assertEqual(metadata['file_info']['total_rows'], 3)
        self.assertEqual(metadata['file_info']['total_columns'], 8)
        
        # Check columns
        self.assertEqual(len(metadata['columns']), 8)
        
        # Check schema summary
        self.assertIsInstance(metadata['schema_summary']['numeric_columns_count'], int)
    
    def test_save_metadata(self):
        """Test metadata saving to JSON file."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        extractor.extract_metadata()
        
        output_file = os.path.join(self.temp_dir, "test_output.json")
        saved_path = extractor.save_metadata(output_file)
        
        self.assertEqual(saved_path, output_file)
        self.assertTrue(os.path.exists(output_file))
        
        # Verify JSON content
        with open(output_file, 'r') as f:
            saved_metadata = json.load(f)
        
        self.assertIn('file_info', saved_metadata)
        self.assertIn('columns', saved_metadata)
        self.assertIn('schema_summary', saved_metadata)
    
    def test_save_metadata_default_name(self):
        """Test metadata saving with default filename."""
        extractor = CSVMetadataExtractor(self.test_file_1)
        extractor.extract_metadata()
        
        saved_path = extractor.save_metadata()
        
        self.assertIsInstance(saved_path, str)
        self.assertTrue(os.path.exists(saved_path))
        self.assertTrue(saved_path.endswith('_metadata.json'))
        
        # Clean up
        os.remove(saved_path)
    
    def test_extract_metadata_error_handling(self):
        """Test error handling in metadata extraction."""
        extractor = CSVMetadataExtractor("non_existent_file.csv")
        metadata = extractor.extract_metadata()
        
        self.assertIn('error', metadata)
        self.assertIn('Failed to load CSV file', metadata['error'])


if __name__ == '__main__':
    unittest.main() 