"""
Data Processing Script

Script to process data files using the new clean architecture.
"""

import os
import sys
import glob
from pathlib import Path

# Add the sources directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Api.Application.services import DataProcessingService
from Api.Infrastructure.mongodb_connector import MongoDBConnector
from Api.Domain.dtos import ProcessFileRequest, ProcessDirectoryRequest


def main():
    """Main function to process data files."""
    
    # Initialize MongoDB connector
    mongodb_connector = MongoDBConnector()
    
    # Connect to MongoDB
    if not mongodb_connector.connect():
        print("Failed to connect to MongoDB. Please ensure MongoDB is running.")
        return
    
    try:
        # Initialize data processing service
        data_service = DataProcessingService(mongodb_connector)
        
        # Get the sample data directory
        sample_data_dir = Path(__file__).parent.parent / "sample_data"
        
        if not sample_data_dir.exists():
            print(f"Sample data directory not found: {sample_data_dir}")
            return
        
        print(f"Processing files from: {sample_data_dir}")
        print("=" * 50)
        
        # Process all CSV and XLSX files
        csv_files = list(sample_data_dir.glob("*.csv"))
        xlsx_files = list(sample_data_dir.glob("*.xlsx"))
        xls_files = list(sample_data_dir.glob("*.xls"))
        
        all_files = csv_files + xlsx_files + xls_files
        
        if not all_files:
            print("No CSV or XLSX files found in the sample data directory.")
            return
        
        # Process each file
        for file_path in all_files:
            print(f"\nProcessing: {file_path.name}")
            print("-" * 30)
            
            try:
                # Create processing request
                request = ProcessFileRequest(file_path=str(file_path))
                
                # Process the file
                response = data_service.process_file(request)
                
                if response.success:
                    print(f"✅ Successfully processed {file_path.name}")
                    print(f"   Collection: {response.data['collection_name']}")
                    print(f"   Rows processed: {response.data['rows_processed']}")
                    print(f"   Rows inserted: {response.data['rows_inserted']}")
                    print(f"   File info: {response.data['file_info']['file_name']}")
                    print(f"   Total rows: {response.data['file_info']['total_rows']}")
                    print(f"   Total columns: {response.data['file_info']['total_columns']}")
                else:
                    print(f"❌ Failed to process {file_path.name}")
                    print(f"   Error: {response.error}")
                    
            except Exception as e:
                print(f"❌ Error processing {file_path.name}: {str(e)}")
        
        # Get processing status
        print("\n" + "=" * 50)
        print("PROCESSING STATUS")
        print("=" * 50)
        
        status = data_service.get_processing_status()
        
        if status.success:
            print(f"Total collections: {status.total_collections}")
            print("\nCollections:")
            for collection in status.collections:
                print(f"  📊 {collection['collection_name']}")
                print(f"     Documents: {collection['document_count']:,}")
                print(f"     Storage: {collection['storage_size'] / 1024 / 1024:.2f} MB")
                print(f"     Index: {collection['index_size'] / 1024:.2f} KB")
                if collection['created_at']:
                    print(f"     Created: {collection['created_at']}")
                print()
        else:
            print(f"Failed to get status: {status.error}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
    
    finally:
        # Disconnect from MongoDB
        mongodb_connector.disconnect()
        print("\nDisconnected from MongoDB.")


if __name__ == "__main__":
    main() 