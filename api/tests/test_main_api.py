#!/usr/bin/env python3
"""
Unit tests for Main API.

Tests the MetadataExtractionAPI class and main functionality.
"""

import unittest
import tempfile
import os
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import MetadataExtractionAPI


class TestMetadataExtractionAPI(unittest.TestCase):
    """Test cases for MetadataExtractionAPI class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.api = MetadataExtractionAPI()
        
        # Create test CSV files
        self.create_test_files()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def create_test_files(self):
        """Create test CSV files."""
        
        # Test file 1: Employee data
        self.test_file_1 = os.path.join(self.temp_dir, "employees.csv")
        with open(self.test_file_1, 'w') as f:
            f.write("id,name,age,salary,department,hire_date,is_active\n")
            f.write("1,John Doe,30,75000.50,Engineering,2023-01-15,true\n")
            f.write("2,Jane Smith,28,82000.75,Marketing,2023-02-20,true\n")
            f.write("3,Bob Johnson,35,95000.25,Engineering,2022-11-10,false\n")
        
        # Test file 2: Product data
        self.test_file_2 = os.path.join(self.temp_dir, "products.csv")
        with open(self.test_file_2, 'w') as f:
            f.write("product_id,name,price,category,stock\n")
            f.write("1,Laptop,1200.00,Electronics,50\n")
            f.write("2,Desk Chair,299.99,Furniture,25\n")
            f.write("3,Notebook,15.50,Office,100\n")
        
        # Test file 3: Sales data
        self.test_file_3 = os.path.join(self.temp_dir, "sales.csv")
        with open(self.test_file_3, 'w') as f:
            f.write("sale_id,product_id,quantity,total_amount,sale_date\n")
            f.write("1,1,2,2400.00,2023-01-15\n")
            f.write("2,2,1,299.99,2023-01-16\n")
            f.write("3,3,5,77.50,2023-01-17\n")
    
    def test_api_initialization(self):
        """Test API initialization."""
        self.assertIsInstance(self.api.extractors, dict)
        self.assertEqual(len(self.api.extractors), 0)
    
    def test_extract_metadata_single_file(self):
        """Test single file metadata extraction."""
        metadata = self.api.extract_metadata(self.test_file_1)
        
        self.assertIsInstance(metadata, dict)
        self.assertIn('file_info', metadata)
        self.assertIn('columns', metadata)
        self.assertIn('schema_summary', metadata)
        
        # Check file info
        self.assertEqual(metadata['file_info']['file_name'], 'employees.csv')
        self.assertEqual(metadata['file_info']['total_rows'], 3)
        self.assertEqual(metadata['file_info']['total_columns'], 7)
        
        # Check that extractor was stored
        self.assertIn(self.test_file_1, self.api.extractors)
    
    def test_extract_metadata_with_output_path(self):
        """Test metadata extraction with output path."""
        output_path = os.path.join(self.temp_dir, "test_output.json")
        metadata = self.api.extract_metadata(self.test_file_1, output_path)
        
        self.assertTrue(os.path.exists(output_path))
        
        # Verify saved content
        with open(output_path, 'r') as f:
            saved_metadata = json.load(f)
        
        self.assertEqual(metadata['file_info']['file_name'], saved_metadata['file_info']['file_name'])
    
    def test_extract_metadata_with_pretty_print(self):
        """Test metadata extraction with pretty print."""
        # Capture stdout to test pretty print
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            metadata = self.api.extract_metadata(self.test_file_1, pretty_print=True)
        
        output = f.getvalue()
        
        # Check that pretty print output contains expected sections
        self.assertIn("CSV METADATA EXTRACTION RESULTS", output)
        self.assertIn("FILE INFORMATION", output)
        self.assertIn("SCHEMA SUMMARY", output)
        self.assertIn("COLUMN DETAILS", output)
        
        # Verify metadata was still returned
        self.assertIsInstance(metadata, dict)
        self.assertIn('file_info', metadata)
    
    def test_extract_metadata_file_not_found(self):
        """Test metadata extraction with non-existent file."""
        with self.assertRaises(FileNotFoundError):
            self.api.extract_metadata("non_existent_file.csv")
    
    def test_extract_multiple_files(self):
        """Test multiple file processing."""
        files = [self.test_file_1, self.test_file_2, self.test_file_3]
        results = self.api.extract_multiple_files(files)
        
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), 3)
        
        # Check that all files were processed successfully
        for file_path, result in results.items():
            self.assertIn('file_info', result)
            self.assertIn('columns', result)
            self.assertIn('schema_summary', result)
    
    def test_extract_multiple_files_with_output_dir(self):
        """Test multiple file processing with output directory."""
        files = [self.test_file_1, self.test_file_2]
        output_dir = os.path.join(self.temp_dir, "metadata_output")
        
        results = self.api.extract_multiple_files(files, output_dir)
        
        # Check that output directory was created
        self.assertTrue(os.path.exists(output_dir))
        
        # Check that metadata files were created
        expected_files = [
            os.path.join(output_dir, "employees_metadata.json"),
            os.path.join(output_dir, "products_metadata.json")
        ]
        
        for expected_file in expected_files:
            self.assertTrue(os.path.exists(expected_file))
        
        # Verify results
        self.assertEqual(len(results), 2)
        for file_path, result in results.items():
            self.assertNotIn('error', result)
    
    def test_extract_multiple_files_with_errors(self):
        """Test multiple file processing with some files having errors."""
        files = [self.test_file_1, "non_existent_file.csv", self.test_file_2]
        results = self.api.extract_multiple_files(files)
        
        self.assertEqual(len(results), 3)
        
        # Check successful files
        self.assertNotIn('error', results[self.test_file_1])
        self.assertNotIn('error', results[self.test_file_2])
        
        # Check failed file
        self.assertIn('error', results["non_existent_file.csv"])
    
    def test_compare_schemas(self):
        """Test schema comparison functionality."""
        files = [self.test_file_1, self.test_file_2, self.test_file_3]
        comparison = self.api.compare_schemas(files)
        
        self.assertIsInstance(comparison, dict)
        self.assertIn('files_analyzed', comparison)
        self.assertIn('total_files', comparison)
        self.assertIn('schema_comparison', comparison)
        self.assertIn('common_columns', comparison)
        self.assertIn('unique_columns', comparison)
        
        # Check counts
        self.assertEqual(comparison['total_files'], 3)
        self.assertEqual(comparison['files_analyzed'], 3)
        
        # Check that common and unique columns are lists
        self.assertIsInstance(comparison['common_columns'], list)
        self.assertIsInstance(comparison['unique_columns'], list)
    
    def test_compare_schemas_with_errors(self):
        """Test schema comparison with some files having errors."""
        files = [self.test_file_1, "non_existent_file.csv", self.test_file_2]
        comparison = self.api.compare_schemas(files)
        
        self.assertEqual(comparison['total_files'], 3)
        self.assertEqual(comparison['files_analyzed'], 2)  # One file failed
        
        # Should still have comparison data for successful files
        self.assertIsInstance(comparison['common_columns'], list)
        self.assertIsInstance(comparison['unique_columns'], list)
    
    def test_compare_schemas_empty_list(self):
        """Test schema comparison with empty file list."""
        comparison = self.api.compare_schemas([])
        
        self.assertEqual(comparison['total_files'], 0)
        self.assertEqual(comparison['files_analyzed'], 0)
        self.assertEqual(len(comparison['common_columns']), 0)
        self.assertEqual(len(comparison['unique_columns']), 0)
    
    def test_print_metadata(self):
        """Test metadata printing functionality."""
        import io
        from contextlib import redirect_stdout
        
        # Extract metadata first
        metadata = self.api.extract_metadata(self.test_file_1)
        
        # Test printing
        f = io.StringIO()
        with redirect_stdout(f):
            self.api._print_metadata(metadata)
        
        output = f.getvalue()
        
        # Check that output contains expected sections
        self.assertIn("CSV METADATA EXTRACTION RESULTS", output)
        self.assertIn("FILE INFORMATION", output)
        self.assertIn("SCHEMA SUMMARY", output)
        self.assertIn("COLUMN DETAILS", output)
    
    def test_extractors_storage(self):
        """Test that extractors are properly stored."""
        # Extract metadata from multiple files
        self.api.extract_metadata(self.test_file_1)
        self.api.extract_metadata(self.test_file_2)
        
        # Check that extractors were stored
        self.assertEqual(len(self.api.extractors), 2)
        self.assertIn(self.test_file_1, self.api.extractors)
        self.assertIn(self.test_file_2, self.api.extractors)
        
        # Check that stored extractors are valid
        for extractor in self.api.extractors.values():
            self.assertIsNotNone(extractor.df)
            self.assertIsInstance(extractor.metadata, dict)


if __name__ == '__main__':
    unittest.main() 