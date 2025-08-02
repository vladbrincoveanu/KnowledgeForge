"""
Application Services

This module provides backward compatibility by importing services from the services package.
For new code, import directly from the specific service modules.
"""

# Import services from the services package
from .services.data_processing_service import DataProcessingService
from .services.query_service import QueryService
from .services.file_processor_service import FileProcessorService

# Re-export for backward compatibility
__all__ = [
    'DataProcessingService',
    'QueryService',
    'FileProcessorService'
] 