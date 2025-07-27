"""
CSV Metadata Extractor API

A scalable Python API for extracting comprehensive metadata schema from CSV files.
Built with a clean architecture that separates concerns and enables easy extension.
"""

from .csv_metadata_extractor import CSVMetadataExtractor
from .main import MetadataExtractionAPI

__version__ = "1.0.0"
__author__ = "KnowledgeForge Team"

__all__ = [
    "CSVMetadataExtractor",
    "MetadataExtractionAPI"
] 