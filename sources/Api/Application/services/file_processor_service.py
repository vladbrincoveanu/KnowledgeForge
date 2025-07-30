"""
File Processor Service

Service responsible for processing individual files (CSV, XLSX) and
converting them to DataRow objects for storage in MongoDB.
"""

import pandas as pd
from typing import Optional
from datetime import datetime
import logging

from ...Domain.models import ProcessingResult, DataRow
from ...Infrastructure.mongodb_connector import MongoDBConnector
from ...Infrastructure.csv_metadata_extractor import CSVMetadataExtractor
from ...Infrastructure.xlsx_metadata_extractor import XLSXMetadataExtractor

logger = logging.getLogger(__name__)


class FileProcessorService:
    """Service for processing individual files and converting them to DataRow objects."""
    
    def __init__(self, mongodb_connector: MongoDBConnector):
        """
        Initialize the service with a MongoDB connector.
        
        Args:
            mongodb_connector (MongoDBConnector): MongoDB connection handler
        """
        self.mongodb_connector = mongodb_connector
    
    def process_file(self, file_path: str, collection_name: str, 
                    sheet_name: Optional[str] = None) -> ProcessingResult:
        """
        Process a file and store its data in MongoDB.
        
        Args:
            file_path (str): Path to the file to process
            collection_name (str): Name of the MongoDB collection
            sheet_name (Optional[str]): Sheet name for Excel files
            
        Returns:
            ProcessingResult: Processing result
        """
        try:
            # Determine file type and process accordingly
            if file_path.lower().endswith('.csv'):
                return self._process_csv_file(file_path, collection_name)
            elif file_path.lower().endswith(('.xlsx', '.xls')):
                return self._process_xlsx_file(file_path, collection_name, sheet_name)
            else:
                return ProcessingResult(
                    success=False,
                    file_path=file_path,
                    collection_name=collection_name,
                    rows_processed=0,
                    rows_inserted=0,
                    metadata=None,
                    error=f"Unsupported file type: {file_path}"
                )
                
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return ProcessingResult(
                success=False,
                file_path=file_path,
                collection_name=collection_name,
                rows_processed=0,
                rows_inserted=0,
                metadata=None,
                error=str(e)
            )
    
    def _process_csv_file(self, file_path: str, collection_name: str) -> ProcessingResult:
        """Process a CSV file."""
        try:
            # Extract metadata
            extractor = CSVMetadataExtractor(file_path)
            metadata = extractor.extract_metadata()
            
            if not metadata:
                return ProcessingResult(
                    success=False,
                    file_path=file_path,
                    collection_name=collection_name,
                    rows_processed=0,
                    rows_inserted=0,
                    metadata=None,
                    error="Failed to extract metadata"
                )
            
            # Create collection
            if not self.mongodb_connector.create_collection(collection_name, metadata):
                return ProcessingResult(
                    success=False,
                    file_path=file_path,
                    collection_name=collection_name,
                    rows_processed=0,
                    rows_inserted=0,
                    metadata=metadata,
                    error="Failed to create collection"
                )
            
            # Load data and convert to DataRow objects
            df = pd.read_csv(file_path)
            data_rows = self._convert_dataframe_to_rows(df, metadata)
            
            # Insert data
            rows_inserted = self.mongodb_connector.insert_data_rows(
                collection_name, data_rows
            )
            
            return ProcessingResult(
                success=True,
                file_path=file_path,
                collection_name=collection_name,
                rows_processed=len(df),
                rows_inserted=rows_inserted,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error processing CSV file {file_path}: {e}")
            return ProcessingResult(
                success=False,
                file_path=file_path,
                collection_name=collection_name,
                rows_processed=0,
                rows_inserted=0,
                metadata=None,
                error=str(e)
            )
    
    def _process_xlsx_file(self, file_path: str, collection_name: str, 
                          sheet_name: Optional[str] = None) -> ProcessingResult:
        """Process an XLSX file."""
        try:
            # Extract metadata
            extractor = XLSXMetadataExtractor(file_path)
            all_metadata = extractor.extract_metadata()
            
            if not all_metadata:
                return ProcessingResult(
                    success=False,
                    file_path=file_path,
                    collection_name=collection_name,
                    rows_processed=0,
                    rows_inserted=0,
                    metadata=None,
                    error="Failed to extract metadata"
                )
            
            # If no sheet specified, use the first one
            if not sheet_name:
                sheet_name = list(all_metadata.keys())[0]
            
            if sheet_name not in all_metadata:
                return ProcessingResult(
                    success=False,
                    file_path=file_path,
                    collection_name=collection_name,
                    rows_processed=0,
                    rows_inserted=0,
                    metadata=None,
                    error=f"Sheet '{sheet_name}' not found. Available sheets: {list(all_metadata.keys())}"
                )
            
            metadata = all_metadata[sheet_name]
            
            # Create collection
            if not self.mongodb_connector.create_collection(collection_name, metadata):
                return ProcessingResult(
                    success=False,
                    file_path=file_path,
                    collection_name=collection_name,
                    rows_processed=0,
                    rows_inserted=0,
                    metadata=metadata,
                    error="Failed to create collection"
                )
            
            # Load data and convert to DataRow objects
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            data_rows = self._convert_dataframe_to_rows(df, metadata)
            
            # Insert data
            rows_inserted = self.mongodb_connector.insert_data_rows(
                collection_name, data_rows
            )
            
            return ProcessingResult(
                success=True,
                file_path=file_path,
                collection_name=collection_name,
                rows_processed=len(df),
                rows_inserted=rows_inserted,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error processing XLSX file {file_path}: {e}")
            return ProcessingResult(
                success=False,
                file_path=file_path,
                collection_name=collection_name,
                rows_processed=0,
                rows_inserted=0,
                metadata=None,
                error=str(e)
            )
    
    def _convert_dataframe_to_rows(self, df: pd.DataFrame, metadata) -> list[DataRow]:
        """
        Convert a pandas DataFrame to a list of DataRow objects.
        
        Args:
            df (pd.DataFrame): The dataframe to convert
            metadata: File metadata containing file info
            
        Returns:
            list[DataRow]: List of DataRow objects
        """
        data_rows = []
        
        for index, row in df.iterrows():
            data_row = DataRow(
                row_id=index + 1,
                data=row.to_dict(),
                file_info=metadata.file_info,
                inserted_at=datetime.now()
            )
            data_rows.append(data_row)
        
        return data_rows 