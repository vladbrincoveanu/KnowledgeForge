#!/usr/bin/env python3
"""
CSV Metadata Extractor

A Python program that extracts comprehensive metadata schema from CSV files.
This includes column information, data types, statistics, and schema details.
"""

import pandas as pd
import json
import sys
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import argparse
from pathlib import Path


class CSVMetadataExtractor:
    """Extract comprehensive metadata from CSV files."""
    
    def __init__(self, csv_path: str):
        """
        Initialize the extractor with a CSV file path.
        
        Args:
            csv_path (str): Path to the CSV file
        """
        self.csv_path = csv_path
        self.df = None
        self.metadata = {}
        
    def load_csv(self) -> bool:
        """
        Load the CSV file into a pandas DataFrame.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    self.df = pd.read_csv(self.csv_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                print(f"Error: Could not read {self.csv_path} with any supported encoding")
                return False
                
            return True
        except Exception as e:
            print(f"Error loading CSV file: {e}")
            return False
    
    def infer_data_type(self, column: pd.Series) -> Dict[str, Any]:
        """
        Infer the data type and characteristics of a column.
        
        Args:
            column (pd.Series): The column to analyze
            
        Returns:
            Dict[str, Any]: Data type information
        """
        # Remove null values for analysis
        non_null_col = column.dropna()
        
        if len(non_null_col) == 0:
            return {
                "type": "unknown",
                "subtype": "all_null",
                "nullable": True,
                "unique_count": 0,
                "sample_values": []
            }
        
        # Check for boolean first (before numeric)
        boolean_values = ['true', 'false', '1', '0', 'yes', 'no', 't', 'f', 'y', 'n']
        if non_null_col.dtype == 'bool' or all(str(x).lower() in boolean_values for x in non_null_col):
            return {
                "type": "boolean",
                "subtype": "bool",
                "nullable": column.isnull().any(),
                "unique_count": non_null_col.nunique(),
                "sample_values": [bool(x) if isinstance(x, (bool, int)) else str(x).lower() in ['true', '1', 'yes', 't', 'y'] for x in non_null_col.head(5)]
            }
        
        # Check for numeric types
        try:
            pd.to_numeric(non_null_col)
            # Check if it's integer
            if all(float(x).is_integer() for x in non_null_col if pd.notna(x)):
                return {
                    "type": "integer",
                    "subtype": "int64",
                    "nullable": column.isnull().any(),
                    "unique_count": non_null_col.nunique(),
                    "min_value": int(non_null_col.min()) if len(non_null_col) > 0 else None,
                    "max_value": int(non_null_col.max()) if len(non_null_col) > 0 else None,
                    "sample_values": non_null_col.head(5).tolist()
                }
            else:
                return {
                    "type": "float",
                    "subtype": "float64",
                    "nullable": column.isnull().any(),
                    "unique_count": non_null_col.nunique(),
                    "min_value": float(non_null_col.min()) if len(non_null_col) > 0 else None,
                    "max_value": float(non_null_col.max()) if len(non_null_col) > 0 else None,
                    "sample_values": non_null_col.head(5).tolist()
                }
        except (ValueError, TypeError):
            pass
        
        # Check for datetime
        try:
            pd.to_datetime(non_null_col, errors='raise')
            return {
                "type": "datetime",
                "subtype": "datetime64[ns]",
                "nullable": column.isnull().any(),
                "unique_count": non_null_col.nunique(),
                "min_value": str(non_null_col.min()) if len(non_null_col) > 0 else None,
                "max_value": str(non_null_col.max()) if len(non_null_col) > 0 else None,
                "sample_values": non_null_col.head(5).tolist()
            }
        except (ValueError, TypeError):
            pass
        
        # Default to string
        return {
            "type": "string",
            "subtype": "object",
            "nullable": column.isnull().any(),
            "unique_count": non_null_col.nunique(),
            "max_length": non_null_col.astype(str).str.len().max() if len(non_null_col) > 0 else 0,
            "sample_values": non_null_col.head(5).tolist()
        }
    
    def extract_column_metadata(self) -> Dict[str, Any]:
        """
        Extract metadata for each column in the CSV.
        
        Returns:
            Dict[str, Any]: Column metadata
        """
        columns_metadata = {}
        
        for column_name in self.df.columns:
            column = self.df[column_name]
            data_type_info = self.infer_data_type(column)
            
            # Calculate null statistics
            null_count = int(column.isnull().sum())
            null_percentage = float((null_count / len(column)) * 100)
            
            columns_metadata[column_name] = {
                "position": list(self.df.columns).index(column_name),
                "total_count": len(column),
                "null_count": null_count,
                "null_percentage": null_percentage,
                **data_type_info
            }
        
        return columns_metadata
    
    def extract_file_metadata(self) -> Dict[str, Any]:
        """
        Extract file-level metadata.
        
        Returns:
            Dict[str, Any]: File metadata
        """
        file_stats = os.stat(self.csv_path)
        
        return {
            "file_name": os.path.basename(self.csv_path),
            "file_path": os.path.abspath(self.csv_path),
            "file_size_bytes": file_stats.st_size,
            "file_size_mb": file_stats.st_size / (1024 * 1024),
            "last_modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
            "total_rows": len(self.df),
            "total_columns": len(self.df.columns),
            "has_duplicates": self.df.duplicated().any(),
            "duplicate_rows_count": self.df.duplicated().sum(),
            "extraction_timestamp": datetime.now().isoformat()
        }
    
    def extract_schema_summary(self) -> Dict[str, Any]:
        """
        Extract schema summary information.
        
        Returns:
            Dict[str, Any]: Schema summary
        """
        numeric_columns = []
        categorical_columns = []
        datetime_columns = []
        boolean_columns = []
        
        for col_name, col_info in self.metadata.get('columns', {}).items():
            if col_info['type'] in ['integer', 'float']:
                numeric_columns.append(col_name)
            elif col_info['type'] == 'datetime':
                datetime_columns.append(col_name)
            elif col_info['type'] == 'boolean':
                boolean_columns.append(col_name)
            else:
                categorical_columns.append(col_name)
        
        return {
            "numeric_columns_count": len(numeric_columns),
            "categorical_columns_count": len(categorical_columns),
            "datetime_columns_count": len(datetime_columns),
            "boolean_columns_count": len(boolean_columns),
            "numeric_columns": numeric_columns,
            "categorical_columns": categorical_columns,
            "datetime_columns": datetime_columns,
            "boolean_columns": boolean_columns
        }
    
    def extract_metadata(self) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from the CSV file.
        
        Returns:
            Dict[str, Any]: Complete metadata dictionary
        """
        if not self.load_csv():
            return {"error": "Failed to load CSV file"}
        
        self.metadata = {
            "file_info": self.extract_file_metadata(),
            "columns": self.extract_column_metadata(),
            "schema_summary": self.extract_schema_summary()
        }
        
        return self.metadata
    
    def save_metadata(self, output_path: Optional[str] = None) -> str:
        """
        Save metadata to a JSON file.
        
        Args:
            output_path (Optional[str]): Path for output file. If None, uses default naming.
            
        Returns:
            str: Path to the saved metadata file
        """
        if not output_path:
            base_name = Path(self.csv_path).stem
            output_path = f"{base_name}_metadata.json"
        
        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # Convert numpy types to Python types for JSON serialization
            def convert_numpy_types(obj):
                if isinstance(obj, dict):
                    return {k: convert_numpy_types(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy_types(item) for item in obj]
                elif hasattr(obj, 'item'):  # numpy types
                    return obj.item()
                else:
                    return obj
            
            serializable_metadata = convert_numpy_types(self.metadata)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_metadata, f, indent=2, ensure_ascii=False)
            return output_path
        except Exception as e:
            print(f"Error saving metadata: {e}")
            return ""


# Example usage when run directly
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python csv_metadata_extractor.py <csv_file>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    extractor = CSVMetadataExtractor(csv_file)
    metadata = extractor.extract_metadata()
    
    if "error" in metadata:
        print(f"Error: {metadata['error']}")
        sys.exit(1)
    
    print("Metadata extracted successfully!")
    print(f"File: {metadata['file_info']['file_name']}")
    print(f"Rows: {metadata['file_info']['total_rows']}")
    print(f"Columns: {metadata['file_info']['total_columns']}") 