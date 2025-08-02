"""
CSV Metadata Extractor

Infrastructure layer component for extracting metadata from CSV files.
"""

import pandas as pd
import json
import sys
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import argparse
from pathlib import Path

from ..Domain.models import (
    DataType, ColumnMetadata, SchemaSummary, FileInfo, FileMetadata
)


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
        self.metadata = None
        
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
                "type": DataType.UNKNOWN,
                "subtype": "all_null",
                "nullable": True,
                "unique_count": 0,
                "sample_values": []
            }
        
        # Check for boolean first (before numeric)
        boolean_values = ['true', 'false', '1', '0', 'yes', 'no', 't', 'f', 'y', 'n']
        if non_null_col.dtype == 'bool' or all(str(x).lower() in boolean_values for x in non_null_col):
            return {
                "type": DataType.BOOLEAN,
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
                    "type": DataType.INTEGER,
                    "subtype": "int64",
                    "nullable": column.isnull().any(),
                    "unique_count": non_null_col.nunique(),
                    "min_value": int(non_null_col.min()) if len(non_null_col) > 0 else None,
                    "max_value": int(non_null_col.max()) if len(non_null_col) > 0 else None,
                    "sample_values": non_null_col.head(5).tolist()
                }
            else:
                return {
                    "type": DataType.FLOAT,
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
                "type": DataType.DATETIME,
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
            "type": DataType.STRING,
            "subtype": "object",
            "nullable": column.isnull().any(),
            "unique_count": non_null_col.nunique(),
            "max_length": non_null_col.astype(str).str.len().max() if len(non_null_col) > 0 else 0,
            "sample_values": non_null_col.head(5).tolist()
        }
    
    def extract_column_metadata(self) -> Dict[str, ColumnMetadata]:
        """
        Extract metadata for each column in the CSV.
        
        Returns:
            Dict[str, ColumnMetadata]: Column metadata
        """
        columns_metadata = {}
        
        for column_name in self.df.columns:
            column = self.df[column_name]
            data_type_info = self.infer_data_type(column)
            
            # Calculate null statistics
            null_count = int(column.isnull().sum())
            null_percentage = float((null_count / len(column)) * 100)
            
            columns_metadata[column_name] = ColumnMetadata(
                name=column_name,
                position=list(self.df.columns).index(column_name),
                data_type=data_type_info["type"],
                subtype=data_type_info["subtype"],
                nullable=data_type_info["nullable"],
                total_count=len(column),
                null_count=null_count,
                null_percentage=null_percentage,
                unique_count=data_type_info["unique_count"],
                min_value=data_type_info.get("min_value"),
                max_value=data_type_info.get("max_value"),
                max_length=data_type_info.get("max_length"),
                sample_values=data_type_info.get("sample_values", [])
            )
        
        return columns_metadata
    
    def extract_file_metadata(self) -> FileInfo:
        """
        Extract file-level metadata.
        
        Returns:
            FileInfo: File metadata
        """
        file_stats = os.stat(self.csv_path)
        
        return FileInfo(
            file_name=os.path.basename(self.csv_path),
            file_path=os.path.abspath(self.csv_path),
            file_size_bytes=file_stats.st_size,
            file_size_mb=file_stats.st_size / (1024 * 1024),
            last_modified=datetime.fromtimestamp(file_stats.st_mtime),
            total_rows=len(self.df),
            total_columns=len(self.df.columns),
            has_duplicates=self.df.duplicated().any(),
            duplicate_rows_count=self.df.duplicated().sum(),
            extraction_timestamp=datetime.now()
        )
    
    def extract_schema_summary(self, columns_metadata: Dict[str, ColumnMetadata]) -> SchemaSummary:
        """
        Extract schema summary information.
        
        Args:
            columns_metadata (Dict[str, ColumnMetadata]): Column metadata
            
        Returns:
            SchemaSummary: Schema summary
        """
        numeric_columns = []
        categorical_columns = []
        datetime_columns = []
        boolean_columns = []
        
        for col_name, col_info in columns_metadata.items():
            if col_info.data_type in [DataType.INTEGER, DataType.FLOAT]:
                numeric_columns.append(col_name)
            elif col_info.data_type == DataType.DATETIME:
                datetime_columns.append(col_name)
            elif col_info.data_type == DataType.BOOLEAN:
                boolean_columns.append(col_name)
            else:
                categorical_columns.append(col_name)
        
        return SchemaSummary(
            numeric_columns_count=len(numeric_columns),
            categorical_columns_count=len(categorical_columns),
            datetime_columns_count=len(datetime_columns),
            boolean_columns_count=len(boolean_columns),
            numeric_columns=numeric_columns,
            categorical_columns=categorical_columns,
            datetime_columns=datetime_columns,
            boolean_columns=boolean_columns
        )
    
    def extract_metadata(self) -> Optional[FileMetadata]:
        """
        Extract comprehensive metadata from the CSV file.
        
        Returns:
            Optional[FileMetadata]: Complete metadata object
        """
        if not self.load_csv():
            return None
        
        file_info = self.extract_file_metadata()
        columns_metadata = self.extract_column_metadata()
        schema_summary = self.extract_schema_summary(columns_metadata)
        
        self.metadata = FileMetadata(
            file_info=file_info,
            columns=columns_metadata,
            schema_summary=schema_summary
        )
        
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
            
            # Convert metadata to dictionary for JSON serialization
            metadata_dict = self._convert_metadata_to_dict(self.metadata)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(metadata_dict, f, indent=2, ensure_ascii=False)
            return output_path
        except Exception as e:
            print(f"Error saving metadata: {e}")
            return ""
    
    def _convert_metadata_to_dict(self, metadata: FileMetadata) -> Dict[str, Any]:
        """Convert FileMetadata to dictionary for JSON serialization."""
        return {
            "file_info": {
                "file_name": metadata.file_info.file_name,
                "file_path": metadata.file_info.file_path,
                "file_size_bytes": metadata.file_info.file_size_bytes,
                "file_size_mb": metadata.file_info.file_size_mb,
                "last_modified": metadata.file_info.last_modified.isoformat(),
                "total_rows": metadata.file_info.total_rows,
                "total_columns": metadata.file_info.total_columns,
                "has_duplicates": metadata.file_info.has_duplicates,
                "duplicate_rows_count": metadata.file_info.duplicate_rows_count,
                "extraction_timestamp": metadata.file_info.extraction_timestamp.isoformat()
            },
            "columns": {
                name: {
                    "name": col.name,
                    "position": col.position,
                    "data_type": col.data_type.value,
                    "subtype": col.subtype,
                    "nullable": col.nullable,
                    "total_count": col.total_count,
                    "null_count": col.null_count,
                    "null_percentage": col.null_percentage,
                    "unique_count": col.unique_count,
                    "min_value": col.min_value,
                    "max_value": col.max_value,
                    "max_length": col.max_length,
                    "sample_values": col.sample_values
                }
                for name, col in metadata.columns.items()
            },
            "schema_summary": {
                "numeric_columns_count": metadata.schema_summary.numeric_columns_count,
                "categorical_columns_count": metadata.schema_summary.categorical_columns_count,
                "datetime_columns_count": metadata.schema_summary.datetime_columns_count,
                "boolean_columns_count": metadata.schema_summary.boolean_columns_count,
                "numeric_columns": metadata.schema_summary.numeric_columns,
                "categorical_columns": metadata.schema_summary.categorical_columns,
                "datetime_columns": metadata.schema_summary.datetime_columns,
                "boolean_columns": metadata.schema_summary.boolean_columns
            }
        }


# Example usage when run directly
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python csv_metadata_extractor.py <csv_file>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    extractor = CSVMetadataExtractor(csv_file)
    metadata = extractor.extract_metadata()
    
    if metadata is None:
        print("Error: Failed to extract metadata")
        sys.exit(1)
    
    print("Metadata extracted successfully!")
    print(f"File: {metadata.file_info.file_name}")
    print(f"Rows: {metadata.file_info.total_rows}")
    print(f"Columns: {metadata.file_info.total_columns}") 