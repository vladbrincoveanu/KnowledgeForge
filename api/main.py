#!/usr/bin/env python3
"""
Main entry point for the CSV Metadata Extractor API.

This module provides a clean interface for extracting metadata from CSV files
and can be easily extended for additional functionality.
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Import our core extractor
from csv_metadata_extractor import CSVMetadataExtractor


class MetadataExtractionAPI:
    """Main API class for CSV metadata extraction operations."""
    
    def __init__(self):
        """Initialize the API."""
        self.extractors = {}
    
    def extract_metadata(self, csv_path: str, output_path: Optional[str] = None, 
                        pretty_print: bool = False) -> Dict[str, Any]:
        """
        Extract metadata from a CSV file.
        
        Args:
            csv_path (str): Path to the CSV file
            output_path (Optional[str]): Path for output JSON file
            pretty_print (bool): Whether to print detailed output
            
        Returns:
            Dict[str, Any]: Extracted metadata
        """
        # Validate input file
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        # Create extractor and extract metadata
        extractor = CSVMetadataExtractor(csv_path)
        metadata = extractor.extract_metadata()
        
        if "error" in metadata:
            raise RuntimeError(f"Failed to extract metadata: {metadata['error']}")
        
        # Store extractor for potential reuse
        self.extractors[csv_path] = extractor
        
        # Pretty print if requested
        if pretty_print:
            self._print_metadata(metadata)
        
        # Save metadata if output path provided
        if output_path:
            saved_path = extractor.save_metadata(output_path)
            if saved_path:
                print(f"✅ Metadata saved to: {saved_path}")
            else:
                print("❌ Failed to save metadata file")
        
        return metadata
    
    def extract_multiple_files(self, csv_files: list, output_dir: Optional[str] = None,
                             pretty_print: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Extract metadata from multiple CSV files.
        
        Args:
            csv_files (list): List of CSV file paths
            output_dir (Optional[str]): Directory to save output files
            pretty_print (bool): Whether to print detailed output
            
        Returns:
            Dict[str, Dict[str, Any]]: Metadata for each file
        """
        results = {}
        
        for csv_file in csv_files:
            try:
                output_path = None
                if output_dir:
                    base_name = Path(csv_file).stem
                    output_path = os.path.join(output_dir, f"{base_name}_metadata.json")
                
                metadata = self.extract_metadata(csv_file, output_path, pretty_print)
                results[csv_file] = metadata
                
            except Exception as e:
                print(f"❌ Error processing {csv_file}: {e}")
                results[csv_file] = {"error": str(e)}
        
        return results
    
    def compare_schemas(self, csv_files: list) -> Dict[str, Any]:
        """
        Compare schemas across multiple CSV files.
        
        Args:
            csv_files (list): List of CSV file paths
            
        Returns:
            Dict[str, Any]: Schema comparison results
        """
        schemas = {}
        
        # Extract metadata for all files
        for csv_file in csv_files:
            try:
                extractor = CSVMetadataExtractor(csv_file)
                metadata = extractor.extract_metadata()
                if "error" not in metadata:
                    schemas[csv_file] = metadata
            except Exception as e:
                print(f"❌ Error processing {csv_file}: {e}")
        
        # Compare schemas
        comparison = {
            "files_analyzed": len(schemas),
            "total_files": len(csv_files),
            "schema_comparison": {},
            "common_columns": set(),
            "unique_columns": set()
        }
        
        if schemas:
            # Find common and unique columns
            all_columns = set()
            for schema in schemas.values():
                all_columns.update(schema['columns'].keys())
            
            common_columns = all_columns.copy()
            for schema in schemas.values():
                common_columns &= set(schema['columns'].keys())
            
            comparison["common_columns"] = list(common_columns)
            comparison["unique_columns"] = list(all_columns - common_columns)
            
            # Compare data types for common columns
            for col in common_columns:
                types = {}
                for file_path, schema in schemas.items():
                    col_info = schema['columns'].get(col, {})
                    types[file_path] = col_info.get('type', 'unknown')
                
                comparison["schema_comparison"][col] = types
        
        return comparison
    
    def _print_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Print metadata in a formatted way.
        
        Args:
            metadata (Dict[str, Any]): Metadata to print
        """
        print("\n" + "="*50)
        print("CSV METADATA EXTRACTION RESULTS")
        print("="*50)
        
        # File info
        print(f"\n📁 FILE INFORMATION:")
        print(f"   File: {metadata['file_info']['file_name']}")
        print(f"   Size: {metadata['file_info']['file_size_mb']:.2f} MB")
        print(f"   Rows: {metadata['file_info']['total_rows']:,}")
        print(f"   Columns: {metadata['file_info']['total_columns']}")
        
        # Schema summary
        print(f"\n📊 SCHEMA SUMMARY:")
        summary = metadata['schema_summary']
        print(f"   Numeric columns: {summary['numeric_columns_count']}")
        print(f"   Categorical columns: {summary['categorical_columns_count']}")
        print(f"   Datetime columns: {summary['datetime_columns_count']}")
        print(f"   Boolean columns: {summary['boolean_columns_count']}")
        
        # Column details
        print(f"\n📋 COLUMN DETAILS:")
        for col_name, col_info in metadata['columns'].items():
            print(f"\n   🔹 {col_name}:")
            print(f"      Type: {col_info['type']} ({col_info['subtype']})")
            print(f"      Nullable: {col_info['nullable']}")
            print(f"      Null count: {col_info['null_count']} ({col_info['null_percentage']:.1f}%)")
            print(f"      Unique values: {col_info['unique_count']}")
            
            if col_info['type'] in ['integer', 'float']:
                print(f"      Range: {col_info['min_value']} to {col_info['max_value']}")
            elif col_info['type'] == 'string':
                print(f"      Max length: {col_info['max_length']} characters")
            
            if col_info['sample_values']:
                samples = col_info['sample_values'][:3]
                print(f"      Sample values: {samples}")


def main():
    """Main function to handle command line arguments and execute the API."""
    parser = argparse.ArgumentParser(
        description="CSV Metadata Extraction API - Extract comprehensive metadata from CSV files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py data.csv
  python main.py data.csv -o metadata.json
  python main.py data.csv --pretty
  python main.py file1.csv file2.csv file3.csv --compare
  python main.py *.csv --output-dir ./metadata
        """
    )
    
    parser.add_argument('csv_files', nargs='+', help='Path(s) to CSV file(s)')
    parser.add_argument('-o', '--output', help='Output file path for single file metadata JSON')
    parser.add_argument('--output-dir', help='Output directory for multiple files')
    parser.add_argument('--pretty', action='store_true', help='Pretty print the metadata to console')
    parser.add_argument('--compare', action='store_true', help='Compare schemas across multiple files')
    parser.add_argument('--save', action='store_true', default=True, help='Save metadata to file (default: True)')
    
    args = parser.parse_args()
    
    # Initialize API
    api = MetadataExtractionAPI()
    
    try:
        if len(args.csv_files) == 1:
            # Single file processing
            csv_file = args.csv_files[0]
            metadata = api.extract_metadata(
                csv_file, 
                args.output, 
                args.pretty
            )
            
            if args.save and not args.output:
                # Auto-save with default naming
                base_name = Path(csv_file).stem
                output_path = f"{base_name}_metadata.json"
                api.extractors[csv_file].save_metadata(output_path)
                print(f"✅ Metadata saved to: {output_path}")
        
        else:
            # Multiple files processing
            if args.compare:
                # Schema comparison mode
                comparison = api.compare_schemas(args.csv_files)
                print("\n" + "="*50)
                print("SCHEMA COMPARISON RESULTS")
                print("="*50)
                print(f"\n📊 Files analyzed: {comparison['files_analyzed']}/{comparison['total_files']}")
                print(f"🔗 Common columns: {len(comparison['common_columns'])}")
                print(f"🔍 Unique columns: {len(comparison['unique_columns'])}")
                
                if comparison['common_columns']:
                    print(f"\n📋 Common columns: {', '.join(comparison['common_columns'])}")
                
                if comparison['unique_columns']:
                    print(f"\n🔍 Unique columns: {', '.join(comparison['unique_columns'])}")
                
                # Save comparison results
                if args.output_dir:
                    os.makedirs(args.output_dir, exist_ok=True)
                    import json
                    comparison_file = os.path.join(args.output_dir, "schema_comparison.json")
                    with open(comparison_file, 'w') as f:
                        json.dump(comparison, f, indent=2)
                    print(f"\n✅ Comparison saved to: {comparison_file}")
            
            else:
                # Batch processing mode
                results = api.extract_multiple_files(
                    args.csv_files,
                    args.output_dir,
                    args.pretty
                )
                
                # Print summary
                successful = sum(1 for r in results.values() if "error" not in r)
                print(f"\n📊 Processing Summary:")
                print(f"   Successful: {successful}/{len(results)}")
                print(f"   Failed: {len(results) - successful}/{len(results)}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 