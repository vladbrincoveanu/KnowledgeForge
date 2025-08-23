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
                (r'^\+?1?[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$', 0.95),
                (r'^\+?[0-9]{1,4}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,4}$', 0.90),
                (r'[0-9]{3}[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}', 0.85)
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
        """Extract entities from CSV data with caching support.
        
        Args:
            file_path: Path to the CSV file
            columns: List of column profiles
            config: Extraction configuration
            
        Returns:
            List of extracted entities
        """
        logger.info(f"Extracting entities from {file_path}")
        
        # Check cache first
        file_hash = self._get_file_hash(file_path)
        cached_entities = self._load_cached_entities(file_hash)
        if cached_entities:
            return cached_entities
        
        entities = []
        
        # Extract entities from each column
        for column in columns:
            col_entities = self._extract_column_entities(file_path, column, config)
            entities.extend(col_entities)
        
        # Detect composite keys and hierarchical entities
        composite_entities = self._detect_composite_keys(file_path, columns, config)
        entities.extend(composite_entities)
        
        hierarchical_entities = self._detect_hierarchical_entities(file_path, columns, config)
        entities.extend(hierarchical_entities)
        
        # Remove duplicates and merge similar entities
        entities = self._deduplicate_entities(entities)
        
        # Log extraction summary
        extraction_methods = {}
        for entity in entities:
            method = entity.attributes.get('extraction_method', 'unknown')
            extraction_methods[method] = extraction_methods.get(method, 0) + 1
        
        logger.info(f"Entity extraction completed. Total entities: {len(entities)}")
        for method, count in extraction_methods.items():
            logger.info(f"  - {method}: {count} entities")
        
        # Cache the results
        self._save_cached_entities(file_hash, entities)
        
        logger.info(f"Extracted {len(entities)} unique entities")
        return entities
    
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
    
    def _extract_regex_entities(self, file_path: str, column: ColumnProfile, 
                               config: Dict[str, Any]) -> List[Entity]:
        """Extract entities using regex patterns for known types."""
        entities = []
        
        # Get sample values from the column
        query = f"""
        SELECT DISTINCT "{column.name}" as value
        FROM read_csv_auto('{file_path}')
        WHERE "{column.name}" IS NOT NULL
        LIMIT {config.get('max_entities_per_column', 100)}
        """
        
        df = self.con.execute(query).df()
        
        for _, row in df.iterrows():
            value = str(row['value']).strip()
            if not value or len(value) < 2:
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
    
    def _extract_id_entities(self, file_path: str, column: ColumnProfile, 
                            config: Dict[str, Any]) -> List[Entity]:
        """Extract entities using statistical analysis for ID columns."""
        entities = []
        
        # Get column statistics
        query = f"""
        SELECT 
            "{column.name}",
            COUNT(*) as count,
            COUNT(DISTINCT "{column.name}") as unique_count
        FROM read_csv_auto('{file_path}')
        WHERE "{column.name}" IS NOT NULL
        GROUP BY "{column.name}"
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
        
        # Get sample values for pattern analysis
        query = f"""
        SELECT DISTINCT "{column.name}" as value
        FROM read_csv_auto('{file_path}')
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
            
            # Use DBSCAN clustering to find similar entities
            clustering = DBSCAN(eps=0.3, min_samples=1, metric='cosine')
            clusters = clustering.fit_predict(embeddings)
            
            # Group entities by cluster
            cluster_groups: Dict[int, List[Entity]] = {}
            for i, cluster_id in enumerate(clusters):
                if cluster_id not in cluster_groups:
                    cluster_groups[cluster_id] = []
                cluster_groups[cluster_id].append(entities[i])
            
            # Merge entities in each cluster
            deduplicated_entities = []
            for cluster in cluster_groups.values():
                if len(cluster) == 1:
                    deduplicated_entities.append(cluster[0])
                else:
                    # Merge cluster entities
                    merged_entity = self._merge_entity_group(cluster)
                    deduplicated_entities.append(merged_entity)
            
            logger.info(f"Embedding-based deduplication: {len(entities)} -> {len(deduplicated_entities)} entities")
            return deduplicated_entities
            
        except Exception as e:
            logger.warning(f"Embedding-based deduplication failed: {e}")
            return entities
    
    def extract_entity_patterns(self, file_path: str, column_name: str) -> Dict[str, Any]:
        """Extract patterns from entity values in a column."""
        query = f"""
        SELECT "{column_name}" as value
        FROM read_csv_auto('{file_path}')
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
