"""Entity extraction module for identifying entities in CSV data."""

import pandas as pd
import duckdb
from typing import Dict, List, Any, Optional, Set, Tuple
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
import numpy as np
import hashlib
import re
import json
from pathlib import Path
from datetime import datetime
import pickle
import os

from .models import Entity, DataType, ColumnProfile
from .llm_manager import LLMManager

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extracts entities from CSV data using various techniques."""
    
    def __init__(self, llm_manager: Optional[LLMManager] = None, cache_dir: Optional[str] = None):
        """Initialize the entity extractor.
        
        Args:
            llm_manager: Optional LLM manager for semantic analysis
            cache_dir: Directory for caching extracted entities
        """
        self.llm_manager = llm_manager
        self.con = duckdb.connect(":memory:")
        self.cache_dir = Path(cache_dir) if cache_dir else None
        
        # Initialize regex patterns for known entity types
        self.regex_patterns = self._initialize_regex_patterns()
        
        # Initialize statistical patterns for ID columns
        self.id_patterns = self._initialize_id_patterns()
        
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def __del__(self):
        """Clean up database connection."""
        if hasattr(self, 'con'):
            self.con.close()
    
    def _initialize_regex_patterns(self) -> Dict[str, List[Tuple[str, float]]]:
        """Initialize regex patterns for known entity types with confidence scores."""
        return {
            'email': [
                (r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', 0.95),
                (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 0.90)
            ],
            'phone': [
                # More specific phone patterns that won't catch percentages
                (r'^\+?1?[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$', 0.95),
                (r'^\+?[0-9]{1,4}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,4}$', 0.90),
                # Exclude patterns that look like percentages (e.g., 63.4, 8.04)
                (r'^(?!\d+\.\d+$)[0-9]{3}[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$', 0.85)
            ],
            'url': [
                (r'^https?://[^\s/$.?#].[^\s]*$', 0.95),
                (r'https?://[^\s/$.?#].[^\s]*', 0.90),
                (r'www\.[^\s/$.?#].[^\s]*', 0.85)
            ],
            'date': [
                (r'^\d{4}-\d{2}-\d{2}$', 0.95),
                (r'^\d{2}/\d{2}/\d{4}$', 0.90),
                (r'^\d{1,2}-\d{1,2}-\d{4}$', 0.85),
                (r'\d{4}-\d{2}-\d{2}', 0.80)
            ],
            'time': [
                (r'^\d{2}:\d{2}:\d{2}$', 0.95),
                (r'^\d{2}:\d{2}$', 0.90),
                (r'\d{2}:\d{2}:\d{2}', 0.85)
            ],
            'uuid': [
                (r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 0.95),
                (r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 0.90)
            ],
            'credit_card': [
                (r'^\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}$', 0.95),
                (r'\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}', 0.90)
            ],
            'postal_code': [
                (r'^\d{5}(-\d{4})?$', 0.95),  # US ZIP
                (r'^[A-Z]\d[A-Z] \d[A-Z]\d$', 0.95),  # Canadian
                (r'^\d{5}$', 0.90)
            ],
            'ssn': [
                (r'^\d{3}-\d{2}-\d{4}$', 0.95),
                (r'\d{3}-\d{2}-\d{4}', 0.90)
            ]
        }
    
    def _initialize_id_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize statistical patterns for identifying ID columns."""
        return {
            'sequential_id': {
                'min_sequential_ratio': 0.8,
                'max_gaps': 0.1,
                'confidence': 0.9
            },
            'uuid_like': {
                'min_uuid_ratio': 0.7,
                'confidence': 0.85
            },
            'hash_like': {
                'min_hash_ratio': 0.8,
                'confidence': 0.8
            },
            'composite_key': {
                'min_separator_ratio': 0.7,
                'confidence': 0.75
            }
        }
    
    def _get_file_hash(self, file_path: str) -> str:
        """Generate hash for file content to enable caching."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to generate file hash: {e}")
            return str(hash(file_path))
    
    def _get_cache_path(self, file_hash: str) -> Optional[Path]:
        """Get cache file path for extracted entities."""
        if not self.cache_dir:
            return None
        return self.cache_dir / f"entities_{file_hash}.pkl"
    
    def _load_cached_entities(self, file_hash: str) -> Optional[List[Entity]]:
        """Load cached entities if available."""
        cache_path = self._get_cache_path(file_hash)
        if not cache_path or not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                cached_data = pickle.load(f)
                if isinstance(cached_data, dict) and 'entities' in cached_data:
                    # Check if cache is still valid (e.g., based on timestamp)
                    cache_time = cached_data.get('timestamp', datetime.min)
                    if datetime.now() - cache_time < pd.Timedelta(hours=24):
                        logger.info(f"Using cached entities for file hash {file_hash}")
                        return cached_data['entities']
        except Exception as e:
            logger.warning(f"Failed to load cached entities: {e}")
        
        return None
    
    def _save_cached_entities(self, file_hash: str, entities: List[Entity]):
        """Save extracted entities to cache."""
        cache_path = self._get_cache_path(file_hash)
        if not cache_path:
            return
        
        try:
            cache_data = {
                'entities': entities,
                'timestamp': datetime.now(),
                'count': len(entities)
            }
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            logger.info(f"Cached {len(entities)} entities for file hash {file_hash}")
        except Exception as e:
            logger.warning(f"Failed to cache entities: {e}")
    
    def extract_entities(self, file_path: str, columns: List[ColumnProfile], 
                        config: Dict[str, Any]) -> List[Entity]:
        """Extract entities from CSV data using various techniques."""
        logger.info(f"Extracting entities from {file_path}")
        
        # Use traditional extraction methods for all datasets
        logger.info("Using traditional entity extraction methods")
        return self._extract_entities_traditional(file_path, columns, config)
    
    def _extract_entities_traditional(self, file_path: str, columns: List[ColumnProfile], 
                                     config: Dict[str, Any]) -> List[Entity]:
        """Traditional entity extraction using pattern analysis and regex."""
        entities = []
        
        # Performance optimization: limit processing for large datasets
        max_columns_to_process = config.get('max_columns_to_process', 50)
        if len(columns) > max_columns_to_process:
            logger.info(f"Large dataset detected ({len(columns)} columns). Limiting processing to first {max_columns_to_process} columns for performance.")
            columns = columns[:max_columns_to_process]
        
        # Extract entities for each column
        for column in columns:
            if config.get('use_regex', True):
                regex_entities = self._extract_regex_entities(file_path, column, config)
                entities.extend(regex_entities)
            
            if config.get('use_pattern_analysis', True):
                pattern_entities = self._extract_pattern_entities(file_path, column, config)
                entities.extend(pattern_entities)
            
            if config.get('use_llm_inference', False) and self.llm_manager:
                llm_entities = self._extract_llm_entities(file_path, column, config)
                entities.extend(llm_entities)
        
        # Detect composite keys (with performance limits)
        if config.get('use_composite_key_detection', True):
            composite_entities = self._detect_composite_keys(file_path, columns, config)
            entities.extend(composite_entities)
        
        # Detect hierarchical entities
        if config.get('use_hierarchical_detection', True):
            hierarchical_entities = self._detect_hierarchical_entities(file_path, columns, config)
            entities.extend(hierarchical_entities)
        
        # Use LLM to identify core business entities if available
        if config.get('use_llm_business_entities', True) and self.llm_manager:
            business_entities = self._extract_business_entities_llm(file_path, columns, config)
            entities.extend(business_entities)
        
        # Detect time series patterns
        if config.get('use_time_series_detection', True):
            time_series_entities = self._detect_time_series_patterns(file_path, columns, config)
            entities.extend(time_series_entities)
        
        # Intelligent entity consolidation - NEW GENERIC APPROACH
        if config.get('use_intelligent_consolidation', True):
            entities = self._consolidate_entities_intelligently(file_path, columns, entities, config)
        
        # Deduplicate entities
        entities = self._deduplicate_entities(entities)
        
        # Apply confidence threshold
        confidence_threshold = config.get('confidence_threshold', 0.5)
        entities = [e for e in entities if e.confidence >= confidence_threshold]
        
        # Limit number of entities
        max_entities = config.get('max_entities', 100)
        if len(entities) > max_entities:
            # Sort by confidence and take top entities
            entities.sort(key=lambda x: x.confidence, reverse=True)
            entities = entities[:max_entities]
        
        logger.info(f"Entity extraction completed. Total entities: {len(entities)}")
        return entities
    
    def _consolidate_entities_intelligently(self, file_path: str, columns: List[ColumnProfile], 
                                           entities: List[Entity], config: Dict[str, Any]) -> List[Entity]:
        """Intelligently consolidate entities based on data patterns and relationships."""
        logger.info("Starting intelligent entity consolidation...")
        
        try:
            # Step 1: Analyze dataset structure to identify patterns
            dataset_patterns = self._analyze_dataset_structure(columns)
            
            # Step 2: Group related columns based on patterns
            column_groups = self._group_related_columns(columns, dataset_patterns)
            
            # Step 3: Create consolidated entities from groups
            consolidated_entities = self._create_consolidated_entities(column_groups, dataset_patterns)
            
            # Step 4: Merge with existing entities, replacing redundant ones
            final_entities = self._merge_with_existing_entities(entities, consolidated_entities)
            
            logger.info(f"Intelligent consolidation: {len(entities)} -> {len(final_entities)} entities")
            return final_entities
            
        except Exception as e:
            logger.error(f"Intelligent entity consolidation failed: {e}")
            return entities
    
    def _analyze_dataset_structure(self, columns: List[ColumnProfile]) -> Dict[str, Any]:
        """Analyze dataset structure to identify patterns for entity consolidation."""
        patterns = {
            'time_series': [],
            'location': [],
            'categorical': [],
            'measurement': [],
            'identifier': [],
            'metadata': []
        }
        
        for col in columns:
            col_name = col.name.lower()
            col_type = col.data_type
            
            # Time series detection
            if self._is_time_dimension(col):
                patterns['time_series'].append(col)
            
            # Location detection
            elif self._is_location_dimension(col):
                patterns['location'].append(col)
            
            # Categorical detection
            elif self._is_categorical_dimension(col):
                patterns['categorical'].append(col)
            
            # Measurement detection
            elif self._is_measurement_dimension(col):
                patterns['measurement'].append(col)
            
            # Identifier detection
            elif self._is_identifier_dimension(col):
                patterns['identifier'].append(col)
            
            # Metadata detection
            else:
                patterns['metadata'].append(col)
        
        # Add pattern metadata
        patterns['has_time_series'] = len(patterns['time_series']) > 0
        patterns['has_location'] = len(patterns['location']) > 0
        patterns['has_measurements'] = len(patterns['measurement']) > 0
        patterns['time_series_length'] = len(patterns['time_series'])
        patterns['measurement_columns'] = len(patterns['measurement'])
        
        return patterns
    
    def _is_time_dimension(self, column: ColumnProfile) -> bool:
        """Check if a column represents a time dimension."""
        col_name = column.name
        
        # Check for year columns (e.g., 1991, 1992, 2020)
        if re.match(r'^\d{4}$', col_name) and 1900 <= int(col_name) <= 2100:
            return True
        
        # Check for time-related terms
        time_terms = ['year', 'yr', 'month', 'mon', 'quarter', 'qtr', 'week', 'day', 'date', 'time', 'period']
        if any(term in col_name.lower() for term in time_terms):
            return True
        
        # Check for date-like patterns
        if re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', col_name):
            return True
        
        return False
    
    def _is_location_dimension(self, column: ColumnProfile) -> bool:
        """Check if a column represents a location dimension."""
        col_name = column.name.lower()
        
        # Generic location terms that could apply to any domain
        location_terms = [
            'location', 'place', 'area', 'zone', 'region'
        ]
        
        return any(term in col_name for term in location_terms)
    
    def _is_categorical_dimension(self, column: ColumnProfile) -> bool:
        """Check if a column represents a categorical dimension."""
        col_name = column.name.lower()
        
        categorical_terms = [
            'category', 'type', 'class', 'group', 'level', 'status', 'code', 'id',
            'name', 'description', 'label', 'tag', 'brand', 'model', 'version'
        ]
        
        return any(term in col_name for term in categorical_terms)
    
    def _is_measurement_dimension(self, column: ColumnProfile) -> bool:
        """Check if a column represents a measurement dimension."""
        # Numeric columns that aren't time dimensions are likely measurements
        if column.data_type in [DataType.FLOAT, DataType.INTEGER]:
            if not self._is_time_dimension(column):
                return True
        
        # Check for measurement-related terms
        col_name = column.name.lower()
        measurement_terms = [
            'value', 'amount', 'quantity', 'count', 'number', 'rate', 'ratio', 'percentage',
            'score', 'index', 'metric', 'measure', 'total', 'sum', 'average', 'mean'
        ]
        
        return any(term in col_name for term in measurement_terms)
    
    def _is_identifier_dimension(self, column: ColumnProfile) -> bool:
        """Check if a column represents an identifier dimension."""
        col_name = column.name.lower()
        
        # Check for ID-like patterns
        if re.match(r'.*id$', col_name) or re.match(r'.*_id$', col_name):
            return True
        
        # Check for identifier terms
        identifier_terms = ['id', 'identifier', 'key', 'code', 'reference', 'serial']
        if any(term in col_name for term in identifier_terms):
            return True
        
        # Check if it's a primary key candidate (high uniqueness)
        if column.unique_count > 0 and column.unique_count / (column.unique_count + column.null_count) > 0.9:
            return True
        
        return False
    
    def _group_related_columns(self, columns: List[ColumnProfile], 
                              patterns: Dict[str, Any]) -> Dict[str, List[ColumnProfile]]:
        """Group related columns based on detected patterns."""
        groups = {
            'core_entities': [],
            'time_dimensions': [],
            'measurement_entities': [],
            'location_entities': [],
            'categorical_entities': []
        }
        
        # Group time series columns
        if patterns['time_series']:
            # Sort by year if they're year columns
            year_cols = [col for col in patterns['time_series'] if re.match(r'^\d{4}$', col.name)]
            if year_cols:
                year_cols.sort(key=lambda x: int(x.name))
                groups['time_dimensions'] = year_cols
            else:
                groups['time_dimensions'] = patterns['time_series']
        
        # Group location columns
        if patterns['location']:
            groups['location_entities'] = patterns['location']
        
        # Group categorical columns (potential core entities)
        if patterns['categorical']:
            groups['core_entities'] = patterns['categorical']
        
        # Group measurement columns
        if patterns['measurement']:
            groups['measurement_entities'] = patterns['measurement']
        
        # If no categorical columns, use the first non-time, non-measurement column as core entity
        if not groups['core_entities'] and patterns['metadata']:
            groups['core_entities'] = [patterns['metadata'][0]]
        
        return groups
    
    def _create_consolidated_entities(self, column_groups: Dict[str, List[ColumnProfile]], 
                                     patterns: Dict[str, Any]) -> List[Entity]:
        """Create consolidated entities from column groups."""
        entities = []
        
        try:
            # Create core entity
            if column_groups['core_entities']:
                core_entity = self._create_core_entity(column_groups['core_entities'], patterns)
                if core_entity:
                    entities.append(core_entity)
            
            # Create time dimension entity
            if column_groups['time_dimensions']:
                time_entity = self._create_time_entity(column_groups['time_dimensions'], patterns)
                if time_entity:
                    entities.append(time_entity)
            
            # Create measurement entity
            if column_groups['measurement_entities']:
                measurement_entity = self._create_measurement_entity(
                    column_groups['measurement_entities'], 
                    column_groups['time_dimensions'], 
                    patterns
                )
                if measurement_entity:
                    entities.append(measurement_entity)
            
            # Create location entity
            if column_groups['location_entities']:
                location_entity = self._create_location_entity(column_groups['location_entities'], patterns)
                if location_entity:
                    entities.append(location_entity)
            
            # Create categorical entity
            if column_groups['categorical_entities']:
                cat_entity = self._create_categorical_entity(column_groups['categorical_entities'], patterns)
                if cat_entity:
                    entities.append(cat_entity)
                    
        except Exception as e:
            logger.error(f"Failed to create consolidated entities: {e}")
        
        return entities
    
    def _create_core_entity(self, columns: List[ColumnProfile], patterns: Dict[str, Any]) -> Entity:
        """Create a core entity representing the main object in the dataset."""
        if not columns:
            return None
        
        # Determine entity type based on column characteristics
        entity_type = "core_entity"
        if any('category' in col.name.lower() for col in columns):
            entity_type = "categorical_entity"
        
        # Determine business meaning based on context
        business_meaning = self._infer_business_meaning(columns, patterns)
        
        entity = Entity(
            id=f"core_entity_{hash('core')}",
            name=self._infer_entity_name(columns, patterns),
            entity_type=entity_type,
            attributes={
                "business_meaning": business_meaning,
                "source_columns": [col.name for col in columns],
                "extraction_method": "intelligent_consolidation",
                "entity_category": "core_entity",
                "column_count": len(columns)
            },
            confidence=0.95,
            source_column=columns[0].name
        )
        
        return entity
    
    def _create_time_entity(self, columns: List[ColumnProfile], patterns: Dict[str, Any]) -> Entity:
        """Create a time dimension entity."""
        if not columns:
            return None
        
        # Determine if this is a year-based time series
        is_year_series = all(re.match(r'^\d{4}$', col.name) for col in columns)
        
        if is_year_series:
            # Sort chronologically
            columns.sort(key=lambda x: int(x.name))
            year_range = [int(columns[0].name), int(columns[-1].name)]
            
            entity = Entity(
                id=f"time_series_{hash('time')}",
                name="Year",
                entity_type="temporal_entity",
                attributes={
                    "business_meaning": "Represents the calendar year for which measurements are recorded",
                    "source_columns": [col.name for col in columns],
                    "extraction_method": "intelligent_consolidation",
                    "time_series_type": "yearly",
                    "year_range": year_range,
                    "column_count": len(columns)
                },
                confidence=0.98,
                source_column="time_series"
            )
        else:
            entity = Entity(
                id=f"time_dimension_{hash('time')}",
                name="Time Dimension",
                entity_type="temporal_entity",
                attributes={
                    "business_meaning": "Represents time periods in the dataset",
                    "source_columns": [col.name for col in columns],
                    "extraction_method": "intelligent_consolidation",
                    "time_series_type": "mixed",
                    "column_count": len(columns)
                },
                confidence=0.9,
                source_column="time_dimension"
            )
        
        return entity
    
    def _create_measurement_entity(self, measurement_columns: List[ColumnProfile], 
                                  time_columns: List[ColumnProfile], 
                                  patterns: Dict[str, Any]) -> Entity:
        """Create a measurement entity that consolidates all measurement columns."""
        if not measurement_columns:
            return None
        
        # Infer measurement type and business meaning
        measurement_type = self._infer_measurement_type(measurement_columns, patterns)
        business_meaning = self._infer_measurement_meaning(measurement_columns, time_columns, patterns)
        
        # Determine if this is a time series measurement
        is_time_series = len(time_columns) > 0
        
        entity = Entity(
            id=f"measurement_entity_{hash('measurement')}",
            name=measurement_type,
            entity_type="measurement_entity",
            attributes={
                "business_meaning": business_meaning,
                "source_columns": [col.name for col in measurement_columns],
                "extraction_method": "intelligent_consolidation",
                "entity_category": "measurement_entity",
                "measurement_type": measurement_type,
                "is_time_series": is_time_series,
                "time_columns": [col.name for col in time_columns] if time_columns else [],
                "column_count": len(measurement_columns)
            },
            confidence=0.92,
            source_column="measurement_values"
        )
        
        return entity
    
    def _create_geographic_entity(self, columns: List[ColumnProfile], patterns: Dict[str, Any]) -> Entity:
        """Create a geographic entity."""
        if not columns:
            return None
        
        entity = Entity(
            id=f"geographic_entity_{hash('geo')}",
            name="Geographic Location",
            entity_type="geographic_entity",
            attributes={
                "business_meaning": "Represents geographic locations or regions in the dataset",
                "source_columns": [col.name for col in columns],
                "extraction_method": "intelligent_consolidation",
                "entity_category": "geographic_entity",
                "geographic_types": [self._get_geographic_type(col) for col in columns],
                "column_count": len(columns)
            },
            confidence=0.9,
            source_column=columns[0].name
        )
        
        return entity
    
    def _create_location_entity(self, columns: List[ColumnProfile], patterns: Dict[str, Any]) -> Entity:
        """Create a location entity."""
        if not columns:
            return None
        
        entity = Entity(
            id=f"location_entity_{hash('location')}",
            name="Location",
            entity_type="location_entity",
            attributes={
                "business_meaning": "Represents locations or regions in the dataset",
                "source_columns": [col.name for col in columns],
                "extraction_method": "intelligent_consolidation",
                "entity_category": "location_entity",
                "column_count": len(columns)
            },
            confidence=0.8,
            source_column=columns[0].name
        )
        
        return entity
    
    def _create_categorical_entity(self, columns: List[ColumnProfile], patterns: Dict[str, Any]) -> Entity:
        """Create a categorical entity."""
        if not columns:
            return None
        
        entity = Entity(
            id=f"categorical_entity_{hash('category')}",
            name="Category",
            entity_type="categorical_entity",
            attributes={
                "business_meaning": "Represents classification or categorization dimensions in the dataset",
                "source_columns": [col.name for col in columns],
                "entity_category": "categorical_entity",
                "column_count": len(columns)
            },
            confidence=0.85,
            source_column=columns[0].name
        )
        
        return entity
    
    def _infer_business_meaning(self, columns: List[ColumnProfile], patterns: Dict[str, Any]) -> str:
        """Infer the business meaning of a core entity based on context."""
        if not columns:
            return "Core entity in the dataset"
        
        col_name = columns[0].name.lower()
        
        # Generic business context
        if 'customer' in col_name or 'client' in col_name:
            return "Represents a customer or client"
        elif 'product' in col_name or 'item' in col_name:
            return "Represents a product or item"
        elif 'order' in col_name or 'transaction' in col_name:
            return "Represents an order or transaction"
        
        # Generic context
        else:
            return f"Represents the main {col_name} entity in the dataset"
    
    def _infer_entity_name(self, columns: List[ColumnProfile], patterns: Dict[str, Any]) -> str:
        """Infer a meaningful name for the core entity."""
        if not columns:
            return "Core Entity"
        
        col_name = columns[0].name
        
        # Generic business naming
        if 'customer' in col_name.lower() or 'client' in col_name.lower():
            return "Customer"
        elif 'product' in col_name.lower() or 'item' in col_name.lower():
            return "Product"
        elif 'order' in col_name.lower() or 'transaction' in col_name.lower():
            return "Order"
        
        # Generic naming - capitalize and clean the column name
        else:
            # Convert snake_case or kebab-case to Title Case
            clean_name = col_name.replace('_', ' ').replace('-', ' ').title()
            return clean_name
    
    def _infer_measurement_type(self, columns: List[ColumnProfile], patterns: Dict[str, Any]) -> str:
        """Infer the type of measurement being made."""
        if not columns:
            return "Measurement"
        
        # Check column names for hints
        col_names = [col.name.lower() for col in columns]
        
        # Generic business measurements
        if any(term in ' '.join(col_names) for term in ['sales', 'revenue', 'income', 'profit']):
            return "Sales"
        elif any(term in ' '.join(col_names) for term in ['count', 'number', 'quantity', 'amount']):
            return "Count"
        elif any(term in ' '.join(col_names) for term in ['rate', 'ratio', 'percentage']):
            return "Rate"
        
        # Generic measurement
        else:
            return "Measurement Value"
    
    def _infer_measurement_meaning(self, measurement_columns: List[ColumnProfile], 
                                  time_columns: List[ColumnProfile], 
                                  patterns: Dict[str, Any]) -> str:
        """Infer the business meaning of measurements."""
        measurement_type = self._infer_measurement_type(measurement_columns, patterns)
        
        if time_columns:
            return f"Represents {measurement_type.lower()} values recorded over time for each core entity"
        else:
            return f"Represents {measurement_type.lower()} values for each core entity"
    
    def _merge_with_existing_entities(self, existing_entities: List[Entity], 
                                     consolidated_entities: List[Entity]) -> List[Entity]:
        """Merge consolidated entities with existing ones, replacing redundant ones."""
        if not consolidated_entities:
            return existing_entities
        
        # Create a map of existing entities by type
        existing_by_type = {}
        for entity in existing_entities:
            entity_type = entity.entity_type
            if entity_type not in existing_by_type:
                existing_by_type[entity_type] = []
            existing_by_type[entity_type].append(entity)
        
        # Replace existing entities with consolidated ones
        final_entities = []
        
        for consolidated_entity in consolidated_entities:
            entity_type = consolidated_entity.entity_type
            
            # If we have a consolidated entity of this type, use it instead of existing ones
            if entity_type in existing_by_type:
                # Keep the consolidated entity, skip the existing ones
                final_entities.append(consolidated_entity)
                logger.info(f"Replaced {len(existing_by_type[entity_type])} {entity_type} entities with consolidated entity")
            else:
                # No existing entities of this type, add the consolidated one
                final_entities.append(consolidated_entity)
        
        # Add any existing entities that weren't replaced
        for entity_type, entities in existing_by_type.items():
            if not any(e.entity_type == entity_type for e in consolidated_entities):
                final_entities.extend(entities)
        
        return final_entities
    
    def _extract_regex_entities(self, file_path: str, column: ColumnProfile, 
                               config: Dict[str, Any]) -> List[Entity]:
        """Extract entities using regex patterns for known types."""
        entities = []
        
        # Get sample values from the column using safe CSV reading
        query = f"""
        SELECT DISTINCT CAST("{column.name}" AS VARCHAR) as value
        FROM ({self._safe_read_csv(file_path, [column.name])})
        WHERE "{column.name}" IS NOT NULL
        LIMIT {config.get('max_entities_per_column', 100)}
        """
        
        df = self.con.execute(query).df()
        
        for _, row in df.iterrows():
            value = str(row['value']).strip()
            if not value or len(value) < 2:
                continue
            
            # Check if this looks like a percentage value first
            if self._is_percentage_value(value, column):
                percentage_entity = Entity(
                    id=f"{column.name}_percentage_{hash(value)}",
                    name=f"{column.name}_percentage",
                    entity_type="measurement_entity",
                    attributes={
                        "source_column": column.name,
                        "data_type": column.data_type.value,
                        "extraction_method": "percentage_detection",
                        "measurement_unit": "percentage",
                        "sample_values": [value],
                        "statistical_profile": self._get_statistical_profile(value, column)
                    },
                    confidence=0.85,
                    source_column=column.name,
                    source_value=value
                )
                entities.append(percentage_entity)
                continue
            
            # Test against all regex patterns
            for entity_type, patterns in self.regex_patterns.items():
                for pattern, confidence in patterns:
                    if re.match(pattern, value, re.IGNORECASE):
                        entity = Entity(
                            id=f"{column.name}_{entity_type}_{hash(value)}",
                            name=value,
                            entity_type=entity_type,
                            attributes={
                                "source_column": column.name,
                                "data_type": column.data_type.value,
                                "extraction_method": "regex_pattern",
                                "pattern": pattern,
                                "sample_values": [value],
                                "statistical_profile": self._get_statistical_profile(value, column)
                            },
                            confidence=confidence,
                            source_column=column.name,
                            source_value=value
                        )
                        entities.append(entity)
                        break  # Use first matching pattern
        
        return entities
    
    def _safe_read_csv(self, file_path: str, columns: List[str] = None) -> str:
        """Safely read CSV with explicit type casting to avoid type conversion errors."""
        try:
            if columns:
                # Use explicit type casting to avoid type inference issues
                # Also ensure we're reading with proper headers
                column_list = ', '.join([f'CAST("{col}" AS VARCHAR) as "{col}"' for col in columns])
                return f"SELECT {column_list} FROM read_csv_auto('{file_path}', header=true, auto_detect=true, sample_size=1000)"
            else:
                return f"SELECT * FROM read_csv_auto('{file_path}', header=true, auto_detect=true, sample_size=1000)"
        except Exception as e:
            logger.warning(f"Error in safe CSV reading: {e}")
            # Fallback to basic reading if the advanced method fails
            if columns:
                column_list = ', '.join([f'"{col}"' for col in columns])
                return f"SELECT {column_list} FROM read_csv_auto('{file_path}', header=true)"
            else:
                return f"SELECT * FROM read_csv_auto('{file_path}', header=true)"
    
    def _extract_column_entities(self, file_path: str, column: ColumnProfile, 
                                config: Dict[str, Any]) -> List[Entity]:
        """Extract entities from a single column using multiple strategies."""
        entities = []
        
        # Strategy 1: Regex pattern matching for known types
        regex_entities = self._extract_regex_entities(file_path, column, config)
        entities.extend(regex_entities)
        
        # Strategy 2: Statistical analysis for ID columns
        if column.data_type in [DataType.INTEGER, DataType.STRING]:
            id_entities = self._extract_id_entities(file_path, column, config)
            entities.extend(id_entities)
        
        # Strategy 3: LLM-based semantic analysis
        if self.llm_manager and column.data_type in [DataType.STRING, DataType.CATEGORICAL]:
            try:
                llm_entities = self._extract_llm_entities(file_path, column, config)
                entities.extend(llm_entities)
                logger.debug(f"LLM extraction found {len(llm_entities)} entities for column {column.name}")
            except Exception as e:
                logger.warning(f"LLM-based extraction failed for column {column.name}: {str(e)}")
                logger.info(f"Continuing with other extraction methods for column {column.name}")
                # Continue with other extraction methods instead of failing
        
        # Strategy 4: Pattern-based extraction
        pattern_entities = self._extract_pattern_entities(file_path, column, config)
        entities.extend(pattern_entities)
        
        return entities
    
    def _is_percentage_value(self, value: str, column: ColumnProfile) -> bool:
        """Check if a value looks like a percentage."""
        try:
            # Check if it's a numeric value that could be a percentage
            float_val = float(value)
            
            # If it's a float between 0 and 100, likely a percentage
            if 0 <= float_val <= 100:
                # Additional checks to avoid false positives
                if column.data_type in [DataType.FLOAT, DataType.INTEGER]:
                    # If column name is a year, this is likely a measurement value, not a phone number
                    if re.match(r'^\d{4}$', column.name):
                        return True
                    # If the value has decimal places and is reasonable for percentages
                    if '.' in value and len(value.split('.')[1]) <= 2:
                        return True
            
            return False
        except (ValueError, TypeError):
            return False
    
    def _extract_id_entities(self, file_path: str, column: ColumnProfile, 
                            config: Dict[str, Any]) -> List[Entity]:
        """Extract entities using statistical analysis for ID columns."""
        entities = []
        
        # Get column statistics using safe CSV reading
        query = f"""
        SELECT 
            CAST("{column.name}" AS VARCHAR) as "{column.name}",
            COUNT(*) as count,
            COUNT(DISTINCT CAST("{column.name}" AS VARCHAR)) as unique_count
        FROM ({self._safe_read_csv(file_path, [column.name])})
        WHERE "{column.name}" IS NOT NULL
        GROUP BY CAST("{column.name}" AS VARCHAR)
        ORDER BY count DESC
        LIMIT 1000
        """
        
        df = self.con.execute(query).df()
        
        if df.empty:
            return entities
        
        # Analyze for sequential IDs
        if self._is_sequential_id(df, column):
            entity = Entity(
                id=f"{column.name}_sequential_id_{hash(column.name)}",
                name=f"{column.name}_sequential_id",
                entity_type="sequential_id",
                attributes={
                    "source_column": column.name,
                    "data_type": column.data_type.value,
                    "extraction_method": "statistical_analysis",
                    "sample_values": df[column.name].head(10).tolist(),
                    "statistical_profile": self._get_column_statistics(file_path, column)
                },
                confidence=self.id_patterns['sequential_id']['confidence'],
                source_column=column.name
            )
            entities.append(entity)
        
        # Analyze for UUID-like patterns
        if self._is_uuid_like(df, column):
            entity = Entity(
                id=f"{column.name}_uuid_like_{hash(column.name)}",
                name=f"{column.name}_uuid_like",
                entity_type="uuid_like",
                attributes={
                    "source_column": column.name,
                    "data_type": column.data_type.value,
                    "extraction_method": "statistical_analysis",
                    "sample_values": df[column.name].head(10).tolist(),
                    "statistical_profile": self._get_column_statistics(file_path, column)
                },
                confidence=self.id_patterns['uuid_like']['confidence'],
                source_column=column.name
            )
            entities.append(entity)
        
        return entities
    
    def _is_sequential_id(self, df: pd.DataFrame, column: ColumnProfile) -> bool:
        """Check if column contains sequential IDs."""
        if column.data_type != DataType.INTEGER:
            return False
        
        values = pd.to_numeric(df[column.name], errors='coerce').dropna()
        if len(values) < 10:
            return False
        
        # Check if values are mostly sequential
        sorted_values = sorted(values)
        gaps = [sorted_values[i+1] - sorted_values[i] for i in range(len(sorted_values)-1)]
        
        if not gaps:
            return False
        
        # Calculate ratio of sequential values (gap = 1)
        sequential_count = sum(1 for gap in gaps if gap == 1)
        sequential_ratio = sequential_count / len(gaps)
        
        return sequential_ratio >= self.id_patterns['sequential_id']['min_sequential_ratio']
    
    def _is_uuid_like(self, df: pd.DataFrame, column: ColumnProfile) -> bool:
        """Check if column contains UUID-like values."""
        if column.data_type != DataType.STRING:
            return False
        
        # Check if values match UUID pattern
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        uuid_count = sum(1 for val in df[column.name] if re.match(uuid_pattern, str(val), re.IGNORECASE))
        uuid_ratio = uuid_count / len(df)
        
        return uuid_ratio >= self.id_patterns['uuid_like']['min_uuid_ratio']
    
    def _extract_llm_entities(self, file_path: str, column: ColumnProfile, 
                              config: Dict[str, Any]) -> List[Entity]:
        """Extract entities using LLM semantic analysis."""
        if not self.llm_manager:
            return []
        
        entities = []
        
        # Get sample values for LLM analysis
        query = f"""
        SELECT DISTINCT "{column.name}" as value
        FROM read_csv_auto('{file_path}')
        WHERE "{column.name}" IS NOT NULL
        LIMIT 20
        """
        
        df = self.con.execute(query).df()
        
        if df.empty:
            return entities
        
        # Use LLM to classify entity types
        sample_values = df['value'].astype(str).tolist()
        
        try:
            classification = self.llm_manager.classify_semantic_type(sample_values, column.name)
            if classification and classification.confidence > config.get('min_confidence', 0.7):
                # Create entity based on LLM classification
                entity = Entity(
                    id=f"{column.name}_llm_{hash(column.name)}",
                    name=f"{column.name}_{classification.semantic_type}",
                    entity_type=classification.semantic_type,
                    attributes={
                        "source_column": column.name,
                        "data_type": column.data_type.value,
                        "extraction_method": "llm_inference",
                        "llm_reasoning": classification.reasoning,
                        "alternative_types": classification.alternative_types,
                        "sample_values": sample_values,
                        "statistical_profile": self._get_column_statistics(file_path, column)
                    },
                    confidence=classification.confidence,
                    source_column=column.name
                )
                entities.append(entity)
        except Exception as e:
            logger.warning(f"LLM entity extraction failed for column {column.name}: {e}")
        
        return entities
    
    def _extract_pattern_entities(self, file_path: str, column: ColumnProfile, 
                                 config: Dict[str, Any]) -> List[Entity]:
        """Extract entities using pattern analysis."""
        entities = []
        
        # Get sample values for pattern analysis using safe CSV reading
        query = f"""
        SELECT DISTINCT CAST("{column.name}" AS VARCHAR) as value
        FROM ({self._safe_read_csv(file_path, [column.name])})
        WHERE "{column.name}" IS NOT NULL
        LIMIT 100
        """
        
        df = self.con.execute(query).df()
        
        if df.empty:
            return entities
        
        values = df['value'].astype(str).tolist()
        
        # Analyze patterns
        patterns = self.extract_entity_patterns(file_path, column.name)
        
        # Create pattern-based entity
        if patterns:
            entity = Entity(
                id=f"{column.name}_pattern_{hash(column.name)}",
                name=f"{column.name}_pattern",
                entity_type="pattern_based",
                attributes={
                    "source_column": column.name,
                    "data_type": column.data_type.value,
                    "extraction_method": "pattern_analysis",
                    "sample_values": values[:10],
                    "statistical_profile": patterns
                },
                confidence=0.8,
                source_column=column.name
            )
            entities.append(entity)
        
        return entities
    
    def _detect_composite_keys(self, file_path: str, columns: List[ColumnProfile], 
                               config: Dict[str, Any]) -> List[Entity]:
        """Detect composite keys (combinations of columns that uniquely identify rows)."""
        entities = []
        
        try:
            # Look for columns that might form composite keys
            potential_key_columns = []
            for col in columns:
                # Check for division by zero - only consider columns with non-zero null count
                if col.null_count > 0 and col.unique_count / col.null_count > 0.8:  # High uniqueness ratio
                    potential_key_columns.append(col)
                    logger.debug(f"Column {col.name} selected as potential key (high uniqueness ratio)")
                elif col.null_count == 0 and col.unique_count > 0:  # No nulls, high uniqueness
                    potential_key_columns.append(col)
                    logger.debug(f"Column {col.name} selected as potential key (no nulls, high uniqueness)")
            
            logger.info(f"Found {len(potential_key_columns)} potential key columns for composite key detection")
            
            if len(potential_key_columns) < 2:
                logger.debug("Not enough potential key columns for composite key detection")
                return entities
            
            # Check for composite key patterns
            for i, col1 in enumerate(potential_key_columns):
                for col2 in potential_key_columns[i+1:]:
                    try:
                        if self._is_composite_key(file_path, col1, col2):
                            entity = Entity(
                                id=f"composite_key_{col1.name}_{col2.name}_{hash(col1.name + col2.name)}",
                                name=f"composite_key_{col1.name}_{col2.name}",
                                entity_type="composite_key",
                                attributes={
                                    "source_columns": [col1.name, col2.name],
                                    "extraction_method": "composite_key_detection",
                                    "sample_values": self._get_composite_samples(file_path, col1, col2),
                                    "statistical_profile": {
                                        "column1": col1.name,
                                        "column2": col2.name,
                                        "uniqueness_ratio": self._calculate_composite_uniqueness(file_path, col1, col2)
                                    }
                                },
                                confidence=0.85,
                                source_column=f"{col1.name}+{col2.name}"
                            )
                            entities.append(entity)
                    except Exception as e:
                        logger.warning(f"Failed to process composite key for columns {col1.name} and {col2.name}: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.warning(f"Composite key detection failed: {str(e)}")
            # Return empty list instead of crashing
        
        return entities
    
    def _is_composite_key(self, file_path: str, col1: ColumnProfile, col2: ColumnProfile) -> bool:
        """Check if two columns form a composite key."""
        query = f"""
        SELECT COUNT(*) as total, COUNT(DISTINCT ("{col1.name}", "{col2.name}")) as unique_pairs
        FROM read_csv_auto('{file_path}')
        WHERE "{col1.name}" IS NOT NULL AND "{col2.name}" IS NOT NULL
        """
        
        result = self.con.execute(query).fetchone()
        if not result:
            return False
        
        total, unique_pairs = result
        if total == 0:
            return False
        
        # Check if the combination is highly unique
        uniqueness_ratio = unique_pairs / total
        return uniqueness_ratio >= 0.95
    
    def _get_composite_samples(self, file_path: str, col1: ColumnProfile, col2: ColumnProfile) -> List[str]:
        """Get sample composite key values."""
        query = f"""
        SELECT DISTINCT "{col1.name}", "{col2.name}"
        FROM read_csv_auto('{file_path}')
        WHERE "{col1.name}" IS NOT NULL AND "{col2.name}" IS NOT NULL
        LIMIT 10
        """
        
        df = self.con.execute(query).df()
        return [f"{row[col1.name]}+{row[col2.name]}" for _, row in df.iterrows()]
    
    def _calculate_composite_uniqueness(self, file_path: str, col1: ColumnProfile, col2: ColumnProfile) -> float:
        """Calculate uniqueness ratio for composite key."""
        query = f"""
        SELECT COUNT(*) as total, COUNT(DISTINCT ("{col1.name}", "{col2.name}")) as unique_pairs
        FROM read_csv_auto('{file_path}')
        WHERE "{col1.name}" IS NOT NULL AND "{col2.name}" IS NOT NULL
        """
        
        result = self.con.execute(query).fetchone()
        if not result or result[0] == 0:
            return 0.0
        
        total, unique_pairs = result
        return unique_pairs / total
    
    def _detect_hierarchical_entities(self, file_path: str, columns: List[ColumnProfile], 
                                     config: Dict[str, Any]) -> List[Entity]:
        """Detect hierarchical entities (e.g., address components)."""
        entities = []
        
        try:
            # Look for address-related columns
            address_columns = []
            for col in columns:
                col_lower = col.name.lower()
                if any(term in col_lower for term in ['address', 'street', 'city', 'state', 'country', 'zip', 'postal']):
                    address_columns.append(col)
            
            logger.debug(f"Found {len(address_columns)} address-related columns: {[col.name for col in address_columns]}")
            
            if len(address_columns) >= 2:
                try:
                    # Create hierarchical address entity
                    entity = Entity(
                        id=f"hierarchical_address_{hash('address')}",
                        name="address_hierarchy",
                        entity_type="hierarchical_address",
                        attributes={
                            "source_columns": [col.name for col in address_columns],
                            "extraction_method": "hierarchical_detection",
                            "components": [col.name for col in address_columns],
                            "sample_values": self._get_address_samples(file_path, address_columns),
                            "statistical_profile": {
                                "component_count": len(address_columns),
                                "components": [col.name for col in address_columns]
                            }
                        },
                        confidence=0.9,
                        source_column="address_components"
                    )
                    entities.append(entity)
                    logger.info(f"Created hierarchical address entity with {len(address_columns)} components")
                except Exception as e:
                    logger.warning(f"Failed to create hierarchical address entity: {str(e)}")
            
            # Look for other hierarchical patterns (e.g., product categories)
            category_columns = []
            for col in columns:
                col_lower = col.name.lower()
                if any(term in col_lower for term in ['category', 'type', 'class', 'group', 'level']):
                    category_columns.append(col)
            
            logger.debug(f"Found {len(category_columns)} category-related columns: {[col.name for col in category_columns]}")
            
            if len(category_columns) >= 2:
                try:
                    entity = Entity(
                        id=f"hierarchical_category_{hash('category')}",
                        name="category_hierarchy",
                        entity_type="hierarchical_category",
                        attributes={
                            "source_columns": [col.name for col in category_columns],
                            "extraction_method": "hierarchical_detection",
                            "components": [col.name for col in category_columns],
                            "sample_values": self._get_category_samples(file_path, category_columns),
                            "statistical_profile": {
                                "component_count": len(category_columns),
                                "components": [col.name for col in category_columns]
                            }
                        },
                        confidence=0.85,
                        source_column="category_components"
                    )
                    entities.append(entity)
                    logger.info(f"Created hierarchical category entity with {len(category_columns)} components")
                except Exception as e:
                    logger.warning(f"Failed to create hierarchical category entity: {str(e)}")
                    
        except Exception as e:
            logger.warning(f"Hierarchical entity detection failed: {str(e)}")
            # Return empty list instead of crashing
        
        return entities
    
    def _get_address_samples(self, file_path: str, address_columns: List[ColumnProfile]) -> List[str]:
        """Get sample address values."""
        if not address_columns:
            return []
        
        columns_str = ', '.join([f'"{col.name}"' for col in address_columns])
        query = f"""
        SELECT {columns_str}
        FROM read_csv_auto('{file_path}')
        WHERE {" AND ".join([f'"{col.name}" IS NOT NULL' for col in address_columns])}
        LIMIT 5
        """
        
        df = self.con.execute(query).df()
        return [', '.join([str(row[col.name]) for col in address_columns]) for _, row in df.iterrows()]
    
    def _get_category_samples(self, file_path: str, category_columns: List[ColumnProfile]) -> List[str]:
        """Get sample category values."""
        if not category_columns:
            return []
        
        columns_str = ', '.join([f'"{col.name}"' for col in category_columns])
        query = f"""
        SELECT {columns_str}
        FROM read_csv_auto('{file_path}')
        WHERE {" AND ".join([f'"{col.name}" IS NOT NULL' for col in category_columns])}
        LIMIT 5
        """
        
        df = self.con.execute(query).df()
        return [' > '.join([str(row[col.name]) for col in category_columns]) for _, row in df.iterrows()]
    
    def _get_statistical_profile(self, value: str, column: ColumnProfile) -> Dict[str, Any]:
        """Get statistical profile for a single value."""
        return {
            "length": len(value),
            "word_count": len(value.split()),
            "character_types": {
                "digits": sum(c.isdigit() for c in value),
                "letters": sum(c.isalpha() for c in value),
                "special": sum(not c.isalnum() and not c.isspace() for c in value)
            },
            "data_type": column.data_type.value
        }
    
    def _get_column_statistics(self, file_path: str, column: ColumnProfile) -> Dict[str, Any]:
        """Get comprehensive statistics for a column."""
        query = f"""
        SELECT 
            COUNT(*) as total_count,
            COUNT(DISTINCT "{column.name}") as unique_count,
            COUNT(CASE WHEN "{column.name}" IS NULL THEN 1 END) as null_count,
            MIN(LENGTH(CAST("{column.name}" AS VARCHAR))) as min_length,
            MAX(LENGTH(CAST("{column.name}" AS VARCHAR))) as max_length,
            AVG(LENGTH(CAST("{column.name}" AS VARCHAR))) as avg_length
        FROM read_csv_auto('{file_path}')
        """
        
        result = self.con.execute(query).fetchone()
        if not result:
            return {}
        
        return {
            "total_count": result[0],
            "unique_count": result[1],
            "null_count": result[2],
            "min_length": result[3],
            "max_length": result[4],
            "avg_length": result[5],
            "uniqueness_ratio": result[1] / result[0] if result[0] > 0 else 0
        }
    
    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove duplicate entities and merge similar ones using embedding similarity."""
        if not entities:
            return []
        
        # Group entities by name and entity type
        entity_groups: Dict[str, List[Entity]] = {}
        
        for entity in entities:
            key = f"{entity.name}_{entity.entity_type}"
            if key not in entity_groups:
                entity_groups[key] = []
            entity_groups[key].append(entity)
        
        # Merge entities in each group
        merged_entities = []
        
        for group in entity_groups.values():
            if len(group) == 1:
                merged_entities.append(group[0])
            else:
                # Merge multiple entities with the same name and type
                merged_entity = self._merge_entity_group(group)
                merged_entities.append(merged_entity)
        
        # Use embedding similarity for additional deduplication
        if hasattr(self, 'llm_manager') and self.llm_manager and self.llm_manager.use_embeddings:
            merged_entities = self._deduplicate_by_embeddings(merged_entities)
        
        return merged_entities
    
    def _merge_entity_group(self, entities: List[Entity]) -> Entity:
        """Merge a group of similar entities."""
        if len(entities) == 1:
            return entities[0]
        
        # Use the entity with highest confidence as base
        base_entity = max(entities, key=lambda e: e.confidence)
        
        # Merge attributes
        merged_attributes = base_entity.attributes.copy()
        merged_source_columns = set([base_entity.source_column] if base_entity.source_column else [])
        
        for entity in entities:
            if entity.source_column:
                merged_source_columns.add(entity.source_column)
            
            # Merge attributes, preferring non-None values
            for key, value in entity.attributes.items():
                if key not in merged_attributes or merged_attributes[key] is None:
                    merged_attributes[key] = value
        
        # Update source columns if multiple
        if len(merged_source_columns) > 1:
            merged_attributes['source_columns'] = list(merged_source_columns)
        
        # Create merged entity
        merged_entity = Entity(
            id=base_entity.id,
            name=base_entity.name,
            entity_type=base_entity.entity_type,
            attributes=merged_attributes,
            confidence=base_entity.confidence,
            source_column=base_entity.source_column,
            source_value=base_entity.source_value
        )
        
        return merged_entity
    
    def _deduplicate_by_embeddings(self, entities: List[Entity]) -> List[Entity]:
        """Deduplicate entities using embedding similarity."""
        if not entities or len(entities) < 2:
            return entities
        
        try:
            # Get embeddings for all entity names
            entity_names = [entity.name for entity in entities]
            embeddings = self.llm_manager.embedding_model.encode(entity_names)
            
            # Use simple threshold-based deduplication instead of DBSCAN to avoid sklearn warnings
            similarity_threshold = 0.85
            processed_indices = set()
            clusters = {}
            cluster_id = 0
            
            for i, entity in enumerate(entities):
                if i in processed_indices:
                    continue
                
                # Start a new cluster
                clusters[cluster_id] = [i]
                processed_indices.add(i)
                
                for j in range(i + 1, len(entities)):
                    if j in processed_indices:
                        continue
                    
                    try:
                        # Calculate simple cosine similarity manually
                        if not np.allclose(embeddings[i], 0) and not np.allclose(embeddings[j], 0):
                            # Manual cosine similarity calculation
                            dot_product = np.dot(embeddings[i], embeddings[j])
                            norm_i = np.linalg.norm(embeddings[i])
                            norm_j = np.linalg.norm(embeddings[j])
                            
                            if norm_i > 0 and norm_j > 0:
                                similarity = dot_product / (norm_i * norm_j)
                                if similarity >= similarity_threshold:
                                    clusters[cluster_id].append(j)
                                    processed_indices.add(j)
                    except Exception:
                        # Skip this comparison if it fails
                        continue
                
                cluster_id += 1
            
            # Group entities by cluster
            deduplicated_entities = []
            for cluster_indices in clusters.values():
                if len(cluster_indices) == 1:
                    deduplicated_entities.append(entities[cluster_indices[0]])
                else:
                    # Merge cluster entities
                    cluster_entities = [entities[i] for i in cluster_indices]
                    merged_entity = self._merge_entity_group(cluster_entities)
                    deduplicated_entities.append(merged_entity)
            
            logger.info(f"Embedding-based deduplication: {len(entities)} -> {len(deduplicated_entities)} entities")
            return deduplicated_entities
            
        except Exception as e:
            logger.warning(f"Embedding-based deduplication failed: {e}")
            return entities
    
    def extract_entity_patterns(self, file_path: str, column_name: str) -> Dict[str, Any]:
        """Extract patterns from entity values in a column."""
        query = f"""
        SELECT CAST("{column_name}" AS VARCHAR) as value
        FROM ({self._safe_read_csv(file_path, [column_name])})
        WHERE "{column_name}" IS NOT NULL
        LIMIT 1000
        """
        
        df = self.con.execute(query).df()
        
        if df.empty:
            return {}
        
        # Convert to text for pattern analysis
        values = df['value'].astype(str).tolist()
        
        patterns = {
            "length_distribution": self._analyze_length_distribution(values),
            "character_patterns": self._analyze_character_patterns(values),
            "word_patterns": self._analyze_word_patterns(values),
            "format_patterns": self._analyze_format_patterns(values)
        }
        
        return patterns
    
    def _analyze_length_distribution(self, values: List[str]) -> Dict[str, Any]:
        """Analyze the distribution of value lengths."""
        lengths = [len(val) for val in values]
        return {
            "min_length": min(lengths),
            "max_length": max(lengths),
            "avg_length": sum(lengths) / len(lengths),
            "length_counts": pd.Series(lengths).value_counts().to_dict()
        }
    
    def _analyze_character_patterns(self, values: List[str]) -> Dict[str, Any]:
        """Analyze character patterns in values."""
        all_chars = ''.join(values)
        char_counts = pd.Series(list(all_chars)).value_counts()
        
        return {
            "total_characters": len(all_chars),
            "unique_characters": len(char_counts),
            "most_common_chars": char_counts.head(10).to_dict(),
            "digit_ratio": sum(c.isdigit() for c in all_chars) / len(all_chars) if all_chars else 0,
            "alpha_ratio": sum(c.isalpha() for c in all_chars) / len(all_chars) if all_chars else 0,
            "special_ratio": sum(not c.isalnum() and not c.isspace() for c in all_chars) / len(all_chars) if all_chars else 0
        }
    
    def _analyze_word_patterns(self, values: List[str]) -> Dict[str, Any]:
        """Analyze word patterns in values."""
        all_words = []
        for val in values:
            all_words.extend(val.split())
        
        if not all_words:
            return {}
        
        word_counts = pd.Series(all_words).value_counts()
        
        return {
            "total_words": len(all_words),
            "unique_words": len(word_counts),
            "most_common_words": word_counts.head(10).to_dict(),
            "avg_words_per_value": len(all_words) / len(values)
        }
    
    def _analyze_format_patterns(self, values: List[str]) -> Dict[str, Any]:
        """Analyze format patterns in values."""
        patterns = {
            "email_like": 0,
            "phone_like": 0,
            "date_like": 0,
            "numeric_only": 0,
            "alpha_only": 0,
            "mixed": 0
        }
        
        for value in values:
            if re.match(r'.*@.*\..*', value):
                patterns["email_like"] += 1
            elif re.match(r'[\d\s\-\(\)\+]+', value) and len(re.findall(r'\d', value)) >= 7:
                patterns["phone_like"] += 1
            elif re.match(r'\d{1,4}[-/]\d{1,2}[-/]\d{1,4}', value):
                patterns["date_like"] += 1
            elif value.isdigit():
                patterns["numeric_only"] += 1
            elif value.isalpha():
                patterns["alpha_only"] += 1
            else:
                patterns["mixed"] += 1
        
        # Convert to ratios
        total = len(values)
        if total > 0:
            for key in patterns:
                patterns[key] = patterns[key] / total
        
        return patterns
    
    def get_extraction_summary(self, entities: List[Entity]) -> Dict[str, Any]:
        """Get summary of entity extraction results."""
        if not entities:
            return {}
        
        # Group by extraction method
        method_counts = {}
        type_counts = {}
        confidence_ranges = {"high": 0, "medium": 0, "low": 0}
        
        for entity in entities:
            # Count by extraction method
            method = entity.attributes.get("extraction_method", "unknown")
            method_counts[method] = method_counts.get(method, 0) + 1
            
            # Count by entity type
            type_counts[entity.entity_type] = type_counts.get(entity.entity_type, 0) + 1
            
            # Count by confidence
            if entity.confidence >= 0.8:
                confidence_ranges["high"] += 1
            elif entity.confidence >= 0.6:
                confidence_ranges["medium"] += 1
            else:
                confidence_ranges["low"] += 1
        
        return {
            "total_entities": len(entities),
            "extraction_methods": method_counts,
            "entity_types": type_counts,
            "confidence_distribution": confidence_ranges,
            "avg_confidence": sum(e.confidence for e in entities) / len(entities),
            "unique_source_columns": len(set(e.source_column for e in entities if e.source_column))
        }
    
    def clear_cache(self) -> bool:
        """Clear all cached entities."""
        if not self.cache_dir:
            return False
        
        try:
            cache_files = list(self.cache_dir.glob("entities_*.pkl"))
            for cache_file in cache_files:
                cache_file.unlink()
            
            logger.info(f"Cleared {len(cache_files)} cached entity files")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear entity cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.cache_dir:
            return {"cache_enabled": False}
        
        try:
            cache_files = list(self.cache_dir.glob("entities_*.pkl"))
            cache_sizes = []
            
            for cache_file in cache_files:
                try:
                    cache_sizes.append(cache_file.stat().st_size)
                except:
                    pass
            
            return {
                "cache_enabled": True,
                "cache_dir": str(self.cache_dir),
                "cached_files": len(cache_files),
                "total_cache_size_bytes": sum(cache_sizes),
                "avg_cache_file_size_bytes": sum(cache_sizes) / len(cache_sizes) if cache_sizes else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"cache_enabled": True, "error": str(e)}

    def _extract_business_entities_llm(self, file_path: str, columns: List[ColumnProfile], 
                                      config: Dict[str, Any]) -> List[Entity]:
        """Extract business entities using LLM semantic analysis."""
        if not self.llm_manager:
            return []
        
        entities = []
        
        try:
            # Get sample data for LLM analysis
            sample_data = self._get_sample_data_for_llm(file_path, columns)
            
            # Analyze dataset context for better guidance
            dataset_context = self._analyze_dataset_context(file_path, columns)
            
            # Create prompt for business entity identification
            prompt = self._create_business_entity_prompt(columns, sample_data, dataset_context)
            
            # Use LLM to identify business entities
            business_entities = self.llm_manager.identify_business_entities(prompt, columns)
            
            if business_entities:
                for entity_info in business_entities:
                    entity = self._create_entity_from_llm_analysis(entity_info, columns)
                    if entity:
                        entities.append(entity)
                        logger.info(f"LLM identified business entity: {entity.name} ({entity.entity_type})")
            
        except Exception as e:
            logger.warning(f"LLM business entity extraction failed: {e}")
        
        return entities
    
    def _get_sample_data_for_llm(self, file_path: str, columns: List[ColumnProfile]) -> Dict[str, List[str]]:
        """Get sample data from each column for LLM analysis."""
        sample_data = {}
        
        for column in columns:
            try:
                query = f"""
                SELECT DISTINCT CAST("{column.name}" AS VARCHAR) as value
                FROM ({self._safe_read_csv(file_path, [column.name])})
                WHERE "{column.name}" IS NOT NULL
                LIMIT 10
                """
                
                df = self.con.execute(query).df()
                if not df.empty:
                    sample_data[column.name] = df['value'].astype(str).tolist()
                else:
                    sample_data[column.name] = []
                    
            except Exception as e:
                logger.warning(f"Failed to get sample data for column {column.name}: {e}")
                sample_data[column.name] = []
        
        return sample_data
    
    def _analyze_dataset_context(self, file_path: str, columns: List[ColumnProfile]) -> Dict[str, Any]:
        """Analyze dataset context to provide better guidance to LLM."""
        context = {
            'file_name': os.path.basename(file_path),
            'column_count': len(columns),
            'data_patterns': {},
            'domain_hints': []
        }
        
        try:
            # Analyze column patterns generically
            year_columns = []
            location_columns = []
            measurement_columns = []
            
            for col in columns:
                col_name = col.name.lower()
                
                # Check for year columns
                if col_name.isdigit() and 1900 <= int(col_name) <= 2100:
                    year_columns.append(col.name)
                
                # Check for location columns (generic, not domain-specific)
                if any(term in col_name for term in ['location', 'place', 'area', 'region']):
                    location_columns.append(col.name)
                
                # Check for measurement columns (numeric columns that aren't years)
                if col.data_type in [DataType.FLOAT, DataType.INTEGER] and not col_name.isdigit():
                    measurement_columns.append(col.name)
            
            context['data_patterns'] = {
                'year_columns': year_columns,
                'location_columns': location_columns,
                'measurement_columns': measurement_columns,
                'has_time_series': len(year_columns) > 0,
                'has_location': len(location_columns) > 0
            }
            
            # Generic domain context
            context['domain_context'] = "General dataset analysis for entity identification."
            
        except Exception as e:
            logger.warning(f"Failed to analyze dataset context: {e}")
        
        return context
    
    def _create_business_entity_prompt(self, columns: List[ColumnProfile], 
                                     sample_data: Dict[str, List[str]],
                                     dataset_context: Dict[str, Any]) -> str:
        """Create a prompt for LLM to identify business entities."""
        column_info = []
        for col in columns:
            sample_values = sample_data.get(col.name, [])[:5]  # Limit to 5 samples
            column_info.append(f"- {col.name} ({col.data_type.value}): {sample_values}")
        
        prompt = f"""
        Analyze this CSV dataset and identify the core business entities. Return your response in valid JSON format.

        Columns:
        {chr(10).join(column_info)}

        Dataset Context:
        {dataset_context.get('domain_context', 'General dataset analysis')}
        
        Data Patterns Detected:
        - Time Series: {dataset_context['data_patterns'].get('has_time_series', False)}
        - Location Data: {dataset_context['data_patterns'].get('has_location', False)}
        - Year Columns: {dataset_context['data_patterns'].get('year_columns', [])}
        - Location Columns: {dataset_context['data_patterns'].get('location_columns', [])}

        Please identify and return a JSON object with this structure:
        {{
            "entities": [
                {{
                    "name": "Entity Name",
                    "entity_type": "core_entity|measurement_entity|temporal_entity|geographic_entity|categorical_entity",
                    "source_columns": ["column1", "column2"],
                    "business_meaning": "Description of what this entity represents",
                    "confidence": 0.95
                }}
            ]
        }}

        IMPORTANT GUIDELINES:
        1. **Core Entity**: Identify the main object/concept that the data is about (e.g., Country, Customer, Product)
        2. **Measurement Entity**: Be specific about WHAT is being measured, not just "Measurement Value". 
           - If it's employment data, name it "Employment" or "Agricultural Employment"
           - If it's sales data, name it "Sales" or "Revenue"
           - If it's population data, name it "Population"
        3. **Temporal Entity**: Identify time dimensions (Year, Month, Date, Quarter)
        4. **Geographic Entity**: Identify location dimensions (Country, City, State, Region)
        5. **Categorical Entity**: Identify classification dimensions (Category, Type, Status)

        For the measurement entity, analyze the data values and column context to determine:
        - What specific metric is being measured
        - What units or context the values represent
        - The business domain this data belongs to

        Example: If you see percentage values (like 63.4, 39.8) in year columns, and the context suggests employment data, 
        name the measurement entity "Agricultural Employment" or "Employment Percentage", not just "Measurement Value".

        Return only valid JSON, no additional text.
        """
        
        return prompt
    
    def _create_entity_from_llm_analysis(self, entity_info: Dict[str, Any], 
                                       columns: List[ColumnProfile]) -> Optional[Entity]:
        """Create an Entity object from LLM analysis results."""
        try:
            # Extract entity information from LLM response
            entity_name = entity_info.get('name', 'Unknown')
            entity_type = entity_info.get('entity_type', 'unknown')
            source_columns = entity_info.get('source_columns', [])
            business_meaning = entity_info.get('business_meaning', '')
            confidence = entity_info.get('confidence', 0.7)
            
            # Find actual column names that match the source columns
            actual_source_columns = []
            for col_name in source_columns:
                for col in columns:
                    if col_name.lower() in col.name.lower() or col.name.lower() in col_name.lower():
                        actual_source_columns.append(col.name)
                        break
            
            if not actual_source_columns:
                # If no exact match, use the first column as fallback
                actual_source_columns = [columns[0].name] if columns else []
            
            # Create entity
            entity = Entity(
                id=f"llm_{entity_type}_{hash(entity_name)}",
                name=entity_name,
                entity_type=entity_type,
                attributes={
                    "description": business_meaning,
                    "source_columns": actual_source_columns,
                    "extraction_method": "llm_business_analysis",
                    "business_meaning": business_meaning,
                    "llm_confidence": confidence
                },
                confidence=confidence,
                source_column=actual_source_columns[0] if actual_source_columns else None
            )
            
            return entity
            
        except Exception as e:
            logger.warning(f"Failed to create entity from LLM analysis: {e}")
            return None
    
    def _detect_time_series_patterns(self, file_path: str, columns: List[ColumnProfile], 
                                   config: Dict[str, Any]) -> List[Entity]:
        """Detect time series patterns in the data."""
        entities = []
        
        try:
            # Look for year columns (common time series pattern)
            year_columns = []
            for col in columns:
                if self._is_year_column(col):
                    year_columns.append(col)
            
            if year_columns:
                # Create time series entity
                entity = Entity(
                    id=f"time_series_{hash('year')}",
                    name="Time Series",
                    entity_type="temporal_entity",
                    attributes={
                        "source_columns": [col.name for col in year_columns],
                        "extraction_method": "time_series_detection",
                        "time_columns": [col.name for col in year_columns],
                        "year_range": self._extract_year_range(year_columns),
                        "business_meaning": "Temporal dimension representing time periods in the dataset"
                    },
                    confidence=0.9,
                    source_column="time_series"
                )
                entities.append(entity)
                logger.info(f"Detected time series pattern with {len(year_columns)} year columns")
            
            # Look for other time patterns (months, quarters, etc.)
            time_pattern_columns = []
            for col in columns:
                if self._is_time_pattern_column(col):
                    time_pattern_columns.append(col)
            
            if time_pattern_columns:
                entity = Entity(
                    id=f"time_pattern_{hash('time')}",
                    name="Time Pattern",
                    entity_type="temporal_entity",
                    attributes={
                        "source_columns": [col.name for col in time_pattern_columns],
                        "extraction_method": "time_pattern_detection",
                        "time_patterns": [col.name for col in time_pattern_columns],
                        "business_meaning": "Time-based patterns or periods in the dataset"
                    },
                    confidence=0.8,
                    source_column="time_patterns"
                )
                entities.append(entity)
                
        except Exception as e:
            logger.warning(f"Time series pattern detection failed: {e}")
        
        return entities
    
    def _is_year_column(self, column: ColumnProfile) -> bool:
        """Check if a column represents years."""
        # Check if column name looks like a year
        if re.match(r'^\d{4}$', column.name):
            return True
        
        # Check if column name contains year-related terms
        year_terms = ['year', 'yr', 'annual', 'fiscal']
        if any(term in column.name.lower() for term in year_terms):
            return True
        
        # Check if data type is numeric and values are in reasonable year range
        if column.data_type in [DataType.INTEGER, DataType.FLOAT]:
            # This would require sampling the data, but for now we'll rely on naming
            return False
        
        return False
    
    def _is_time_pattern_column(self, column: ColumnProfile) -> bool:
        """Check if a column represents time patterns."""
        time_terms = ['month', 'quarter', 'week', 'day', 'date', 'period', 'season']
        return any(term in column.name.lower() for term in time_terms)
    
    def _extract_year_range(self, year_columns: List[ColumnProfile]) -> List[int]:
        """Extract the range of years from year columns."""
        years = []
        for col in year_columns:
            try:
                year = int(col.name)
                if 1900 <= year <= 2100:  # Reasonable year range
                    years.append(year)
            except ValueError:
                continue
        
        if years:
            return [min(years), max(years)]
        return []

    def _detect_location_entities(self, file_path: str, columns: List[ColumnProfile], 
                                   config: Dict[str, Any]) -> List[Entity]:
        """Detect location entities in the data (generic, not domain-specific)."""
        entities = []
        
        try:
            # Look for location columns (generic terms only)
            location_columns = []
            for col in columns:
                if self._is_location_column(col):
                    location_columns.append(col)
            
            if location_columns:
                # Create generic location entity
                entity = Entity(
                    id=f"location_{hash('location')}",
                    name="Location",
                    entity_type="location_entity",
                    attributes={
                        "source_columns": [col.name for col in location_columns],
                        "extraction_method": "location_detection",
                        "business_meaning": "Represents locations or regions in the dataset"
                    },
                    confidence=0.8,
                    source_column="location"
                )
                entities.append(entity)
                logger.info(f"Detected location entities in {len(location_columns)} columns")
                
        except Exception as e:
            logger.warning(f"Location entity detection failed: {e}")
        
        return entities
    
    def _is_location_column(self, column: ColumnProfile) -> bool:
        """Check if a column represents location data (generic terms only)."""
        location_terms = [
            'location', 'place', 'area', 'zone', 'region'
        ]
        
        return any(term in column.name.lower() for term in location_terms)
