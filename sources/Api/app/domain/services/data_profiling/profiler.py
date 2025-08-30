"""Data profiling module for CSV datasets."""

import pandas as pd
import duckdb
import hashlib
import re
import json
import pickle
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime
import logging
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
from dataclasses import dataclass

from .models import ColumnProfile, DatasetProfile, DataType

logger = logging.getLogger(__name__)


@dataclass
class ProfileCache:
    """Profile cache entry."""
    file_hash: str
    profile_data: Dict[str, Any]
    timestamp: datetime
    file_size: int
    file_mtime: float


class DataProfiler:
    """Profiles CSV datasets to understand structure and content."""
    
    def __init__(self, duckdb_path: Optional[str] = None, cache_dir: Optional[str] = None):
        """Initialize the data profiler.
        
        Args:
            duckdb_path: Optional path to DuckDB database file
            cache_dir: Directory for profile caching
        """
        self.duckdb_path = duckdb_path or ":memory:"
        self.con = duckdb.connect(self.duckdb_path)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        
        # Regex patterns for common data types
        self.patterns = {
            'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            'phone': re.compile(r'^[\+]?[1-9][\d]{0,15}$'),
            'url': re.compile(r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'),
            'date_iso': re.compile(r'^\d{4}-\d{2}-\d{2}$'),
            'date_us': re.compile(r'^\d{1,2}/\d{1,2}/\d{4}$'),
            'date_eu': re.compile(r'^\d{1,2}-\d{1,2}-\d{4}$'),
            'time': re.compile(r'^\d{2}:\d{2}(:\d{2})?$'),
            'timestamp': re.compile(r'^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}'),
            'uuid': re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE),
            'credit_card': re.compile(r'^\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}$'),
            'postal_code_us': re.compile(r'^\d{5}(-\d{4})?$'),
            'postal_code_uk': re.compile(r'^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$', re.IGNORECASE),
            'ip_address': re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'),
            'ssn': re.compile(r'^\d{3}-\d{2}-\d{4}$'),
            'currency': re.compile(r'^[\$€£¥₹]?\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?$'),
            'percentage': re.compile(r'^\d+(?:\.\d+)?%$'),
            'scientific_notation': re.compile(r'^-?\d+(?:\.\d+)?[eE][+-]?\d+$')
        }
        
        # Semantic type hints based on column names
        self.semantic_hints = {
            'id': ['id', 'identifier', 'key', 'pk', 'primary_key', 'uuid', 'guid'],
            'name': ['name', 'title', 'label', 'description', 'caption'],
            'date': ['date', 'time', 'timestamp', 'created', 'updated', 'modified', 'published'],
            'email': ['email', 'e-mail', 'mail', 'contact_email'],
            'phone': ['phone', 'telephone', 'mobile', 'cell', 'contact_phone'],
            'address': ['address', 'street', 'city', 'state', 'country', 'postal_code', 'zip'],
            'url': ['url', 'link', 'website', 'web', 'uri'],
            'price': ['price', 'cost', 'amount', 'value', 'revenue', 'income'],
            'quantity': ['quantity', 'count', 'number', 'amount', 'total'],
            'category': ['category', 'type', 'class', 'group', 'classification'],
            'status': ['status', 'state', 'condition', 'phase', 'stage']
        }
        
        # Initialize cache if directory provided
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def __del__(self):
        """Clean up database connection."""
        if hasattr(self, 'con'):
            self.con.close()
    
    def profile_dataset(self, file_path: str, sample_size: int = 1000, 
                       use_cache: bool = True, force_refresh: bool = False) -> DatasetProfile:
        """Profile a CSV dataset and return comprehensive profile.
        
        Args:
            file_path: Path to the CSV file
            sample_size: Number of rows to sample for analysis
            use_cache: Whether to use cached profiles
            force_refresh: Force refresh even if cache exists
            
        Returns:
            DatasetProfile object with complete dataset information
        """
        logger.info(f"Profiling dataset: {file_path}")
        
        # Check cache first
        if use_cache and self.cache_dir and not force_refresh:
            cached_profile = self._get_cached_profile(file_path)
            if cached_profile:
                logger.info(f"Using cached profile for {file_path}")
                return cached_profile
        
        try:
            # Get file metadata
            file_info = self._get_file_info(file_path)
            
            # Read dataset with DuckDB for efficient processing
            df = self._read_csv_with_duckdb(file_path, sample_size)
            
            # Generate comprehensive column profiles
            columns = []
            for col_name in df.columns:
                col_profile = self._profile_column_comprehensive(df, col_name, file_path)
                columns.append(col_profile)
            
            # Extract advanced metadata
            metadata = self._extract_comprehensive_metadata(df, file_info)
            
            # Create dataset profile
            profile = DatasetProfile(
                file_path=file_path,
                row_count=len(df),
                column_count=len(df.columns),
                columns=columns,
                created_at=datetime.now().isoformat(),
                metadata=metadata
            )
            
            # Cache the profile
            if use_cache and self.cache_dir:
                self._cache_profile(file_path, profile, file_info)
            
            logger.info(f"Successfully profiled dataset with {len(df)} rows and {len(df.columns)} columns")
            return profile
            
        except Exception as e:
            logger.error(f"Error profiling dataset {file_path}: {str(e)}")
            raise
    
    def _get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get comprehensive file information."""
        path = Path(file_path)
        stat = path.stat()
        
        # Calculate file hash
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read(8192)).hexdigest()  # Read first 8KB for hash
        
        return {
            'file_size': stat.st_size,
            'file_mtime': stat.st_mtime,
            'file_hash': file_hash,
            'file_extension': path.suffix.lower(),
            'file_name': path.name,
            'file_path': str(path.absolute())
        }
    
    def _read_csv_with_duckdb(self, file_path: str, sample_size: int = 1000) -> pd.DataFrame:
        """Read CSV file using DuckDB for efficient processing.
        
        Args:
            file_path: Path to the CSV file
            sample_size: Number of rows to sample (0 for all rows)
            
        Returns:
            Pandas DataFrame with the data
        """
        try:
            # First, read the headers manually to ensure we get the correct column names
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line:
                    # Parse headers manually and clean them
                    headers = [col.strip().strip('"').strip("'") for col in first_line.split(',')]
                    logger.info(f"Detected headers: {headers}")
                    
                    # Use explicit column names with DuckDB
                    if sample_size > 0:
                        query = f"""
                        SELECT * FROM read_csv_auto('{file_path}', 
                            header=false, 
                            names={headers},
                            all_varchar=true)
                        LIMIT {sample_size + 1}
                        """
                    else:
                        query = f"""
                        SELECT * FROM read_csv_auto('{file_path}', 
                            header=false, 
                            names={headers},
                            all_varchar=true)
                        """
                    
                    try:
                        # Execute query and convert to pandas DataFrame
                        result = self.con.execute(query)
                        df = result.df()
                        
                        # Remove the first row (which was the header) since we're not using header=true
                        if len(df) > 0:
                            df = df.iloc[1:].reset_index(drop=True)
                        
                        # Verify column names are correct
                        if list(df.columns) == headers:
                            logger.info(f"Successfully read CSV with manual header handling: {len(df)} rows and {len(df.columns)} columns")
                            logger.debug(f"Column names: {df.columns.tolist()}")
                            return df
                        else:
                            logger.warning(f"Column name mismatch. Expected: {headers}, Got: {list(df.columns)}")
                            raise Exception("Column name mismatch in manual header handling")
                    except Exception as db_error:
                        logger.warning(f"DuckDB query failed: {db_error}")
                        raise Exception(f"DuckDB failed to read CSV: {db_error}")
                else:
                    raise Exception("Could not read CSV headers")
                
        except Exception as duckdb_error:
            logger.warning(f"DuckDB reading failed, falling back to pandas: {duckdb_error}")
            # Fallback to pandas if DuckDB fails
            try:
                if sample_size > 0:
                    df = pd.read_csv(file_path, nrows=sample_size)
                else:
                    df = pd.read_csv(file_path)
                
                logger.info(f"Successfully read CSV file with pandas: {len(df)} rows and {len(df.columns)} columns")
                logger.debug(f"Column names: {df.columns.tolist()}")
                return df
            except Exception as pandas_error:
                logger.error(f"Both DuckDB and pandas failed: {pandas_error}")
                raise Exception(f"Failed to read CSV file with both methods: {str(pandas_error)}")
                
        except Exception as e:
            logger.error(f"Error reading CSV file {file_path}: {str(e)}")
            raise Exception(f"Failed to read CSV file: {str(e)}")
    
    def _profile_column_comprehensive(self, df: pd.DataFrame, column_name: str, 
                                    file_path: str) -> ColumnProfile:
        """Generate comprehensive profile for a single column."""
        col_data = df[column_name]
        
        # Basic statistics
        null_count = col_data.isnull().sum()
        unique_count = col_data.nunique()
        total_count = len(col_data)
        
        # Data type inference
        data_type = self._infer_data_type_advanced(col_data)
        
        # Pattern detection
        patterns = self._detect_patterns(col_data)
        
        # Semantic type hints
        semantic_type = self._infer_semantic_type(column_name, col_data)
        
        # Cardinality analysis
        cardinality = self._analyze_cardinality(unique_count, total_count)
        
        # Value distribution analysis
        distribution = self._analyze_value_distribution(col_data, data_type)
        
        # Potential key analysis
        key_analysis = self._analyze_potential_keys(col_data, unique_count, total_count)
        
        # Advanced statistics
        statistics = self._calculate_comprehensive_statistics(col_data, data_type)
        
        # Sample values with smart sampling
        sample_values = self._get_smart_sample_values(col_data, data_type, unique_count)
        
        return ColumnProfile(
            name=column_name,
            data_type=data_type,
            null_count=int(null_count),
            unique_count=int(unique_count),
            sample_values=sample_values,
            statistics={
                **statistics,
                'patterns': patterns,
                'semantic_type': semantic_type,
                'cardinality': cardinality,
                'distribution': distribution,
                'key_analysis': key_analysis
            }
        )
    
    def _infer_data_type_advanced(self, col_data: pd.Series) -> DataType:
        """Advanced data type inference with pattern detection."""
        clean_data = col_data.dropna()
        
        if len(clean_data) == 0:
            return DataType.STRING
        
        # Check for datetime patterns
        if self._is_datetime_column(col_data):
            return DataType.DATETIME
        
        # Check for numeric types
        if pd.api.types.is_numeric_dtype(col_data):
            if pd.api.types.is_integer_dtype(col_data):
                return DataType.INTEGER
            else:
                return DataType.FLOAT
        
        # Check for boolean
        if pd.api.types.is_bool_dtype(col_data):
            return DataType.BOOLEAN
        
        # Check for categorical (low cardinality)
        unique_ratio = col_data.nunique() / len(col_data)
        if unique_ratio < 0.3:  # More strict threshold
            return DataType.CATEGORICAL
        
        # Check for identifier patterns
        if self._is_identifier_column(col_data):
            return DataType.STRING  # Could be enhanced with IDENTIFIER type
        
        return DataType.STRING
    
    def _is_datetime_column(self, col_data: pd.Series) -> bool:
        """Check if column contains datetime data."""
        # Try pandas datetime conversion
        if pd.api.types.is_datetime64_any_dtype(col_data):
            return True
        
        # Check for datetime patterns in string columns
        if pd.api.types.is_string_dtype(col_data):
            sample_values = col_data.dropna().head(100)
            datetime_count = 0
            
            for value in sample_values:
                if isinstance(value, str):
                    # Check various date formats
                    for pattern_name, pattern in self.patterns.items():
                        if 'date' in pattern_name or 'time' in pattern_name:
                            if pattern.match(value):
                                datetime_count += 1
                                break
            
            # If more than 70% match datetime patterns
            if datetime_count / len(sample_values) > 0.7:
                return True
        
        return False
    
    def _is_identifier_column(self, col_data: pd.Series) -> bool:
        """Check if column contains identifier data."""
        if pd.api.types.is_string_dtype(col_data):
            sample_values = col_data.dropna().head(100)
            id_pattern_count = 0
            
            for value in sample_values:
                if isinstance(value, str):
                    # Check for UUID, email, phone patterns
                    for pattern_name, pattern in self.patterns.items():
                        if pattern_name in ['uuid', 'email', 'phone']:
                            if pattern.match(value):
                                id_pattern_count += 1
                                break
            
            # If more than 50% match identifier patterns
            if id_pattern_count / len(sample_values) > 0.5:
                return True
        
        return False
    
    def _detect_patterns(self, col_data: pd.Series) -> Dict[str, Any]:
        """Detect patterns in column data."""
        patterns = {}
        clean_data = col_data.dropna()
        
        if len(clean_data) == 0:
            return patterns
        
        # Test each pattern
        for pattern_name, pattern in self.patterns.items():
            matches = 0
            total_tested = min(100, len(clean_data))  # Test up to 100 values
            
            for value in clean_data.head(total_tested):
                if isinstance(value, str) and pattern.match(value):
                    matches += 1
            
            match_ratio = matches / total_tested
            if match_ratio > 0.1:  # At least 10% match
                patterns[pattern_name] = {
                    'match_ratio': match_ratio,
                    'match_count': matches,
                    'total_tested': total_tested
                }
        
        # Detect custom patterns
        custom_patterns = self._detect_custom_patterns(clean_data)
        if custom_patterns:
            patterns['custom'] = custom_patterns
        
        return patterns
    
    def _detect_custom_patterns(self, col_data: pd.Series) -> Dict[str, Any]:
        """Detect custom patterns in data."""
        patterns = {}
        
        # Length patterns
        if pd.api.types.is_string_dtype(col_data):
            lengths = [len(str(val)) for val in col_data.head(100)]
            if lengths:
                patterns['length'] = {
                    'min': min(lengths),
                    'max': max(lengths),
                    'mean': np.mean(lengths),
                    'std': np.std(lengths),
                    'distribution': Counter(lengths)
                }
        
        # Character patterns
        if pd.api.types.is_string_dtype(col_data):
            sample_text = ' '.join([str(val) for val in col_data.head(100)])
            if sample_text:
                char_count = len(sample_text)
                digit_count = sum(c.isdigit() for c in sample_text)
                alpha_count = sum(c.isalpha() for c in sample_text)
                space_count = sum(c.isspace() for c in sample_text)
                
                patterns['characters'] = {
                    'total_chars': char_count,
                    'digits': digit_count,
                    'letters': alpha_count,
                    'spaces': space_count,
                    'digit_ratio': digit_count / char_count if char_count > 0 else 0,
                    'alpha_ratio': alpha_count / char_count if char_count > 0 else 0,
                    'space_ratio': space_count / char_count if char_count > 0 else 0
                }
        
        return patterns
    
    def _infer_semantic_type(self, column_name: str, col_data: pd.Series) -> Dict[str, Any]:
        """Infer semantic type based on column name and data patterns."""
        semantic_info = {
            'primary_type': None,
            'confidence': 0.0,
            'name_hints': [],
            'data_hints': [],
            'suggested_type': None
        }
        
        # Check column name hints
        column_lower = column_name.lower()
        name_matches = []
        
        for semantic_type, hints in self.semantic_hints.items():
            for hint in hints:
                if hint in column_lower:
                    name_matches.append(semantic_type)
                    break
        
        if name_matches:
            semantic_info['name_hints'] = name_matches
            semantic_info['confidence'] += 0.4
        
        # Check data pattern hints
        data_matches = []
        if pd.api.types.is_string_dtype(col_data):
            sample_values = col_data.dropna().head(50)
            
            # Check for email patterns
            email_count = sum(1 for val in sample_values 
                            if isinstance(val, str) and self.patterns['email'].match(val))
            if email_count / len(sample_values) > 0.3:
                data_matches.append('email')
            
            # Check for phone patterns
            phone_count = sum(1 for val in sample_values 
                            if isinstance(val, str) and self.patterns['phone'].match(val))
            if phone_count / len(sample_values) > 0.3:
                data_matches.append('phone')
            
            # Check for URL patterns
            url_count = sum(1 for val in sample_values 
                           if isinstance(val, str) and self.patterns['url'].match(val))
            if url_count / len(sample_values) > 0.3:
                data_matches.append('url')
        
        if data_matches:
            semantic_info['data_hints'] = data_matches
            semantic_info['confidence'] += 0.4
        
        # Determine primary type
        all_hints = name_matches + data_matches
        if all_hints:
            # Count occurrences
            hint_counts = Counter(all_hints)
            primary_type = hint_counts.most_common(1)[0][0]
            semantic_info['primary_type'] = primary_type
            semantic_info['suggested_type'] = primary_type
        
        return semantic_info
    
    def _analyze_cardinality(self, unique_count: int, total_count: int) -> Dict[str, Any]:
        """Analyze column cardinality."""
        unique_ratio = unique_count / total_count if total_count > 0 else 0
        
        if unique_ratio == 1.0:
            cardinality_type = "unique"
        elif unique_ratio > 0.8:
            cardinality_type = "high"
        elif unique_ratio > 0.3:
            cardinality_type = "medium"
        elif unique_ratio > 0.1:
            cardinality_type = "low"
        else:
            cardinality_type = "very_low"
        
        return {
            'type': cardinality_type,
            'unique_ratio': unique_ratio,
            'unique_count': unique_count,
            'total_count': total_count
        }
    
    def _analyze_value_distribution(self, col_data: pd.Series, data_type: DataType) -> Dict[str, Any]:
        """Analyze value distribution in column."""
        distribution = {}
        clean_data = col_data.dropna()
        
        if len(clean_data) == 0:
            return distribution
        
        if data_type in [DataType.INTEGER, DataType.FLOAT]:
            # Numeric distribution
            distribution['percentiles'] = {
                'p25': float(np.percentile(clean_data, 25)),
                'p50': float(np.percentile(clean_data, 50)),
                'p75': float(np.percentile(clean_data, 75)),
                'p90': float(np.percentile(clean_data, 90)),
                'p95': float(np.percentile(clean_data, 95)),
                'p99': float(np.percentile(clean_data, 99))
            }
            
            # Check for outliers using IQR method
            q1 = np.percentile(clean_data, 25)
            q3 = np.percentile(clean_data, 75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outliers = clean_data[(clean_data < lower_bound) | (clean_data > upper_bound)]
            distribution['outliers'] = {
                'count': len(outliers),
                'ratio': len(outliers) / len(clean_data),
                'lower_bound': float(lower_bound),
                'upper_bound': float(upper_bound)
            }
        
        elif data_type == DataType.CATEGORICAL:
            # Categorical distribution
            value_counts = clean_data.value_counts()
            distribution['top_values'] = value_counts.head(10).to_dict()
            distribution['value_frequencies'] = {
                'most_common': value_counts.iloc[0] if len(value_counts) > 0 else 0,
                'least_common': value_counts.iloc[-1] if len(value_counts) > 0 else 0
            }
        
        return distribution
    
    def _analyze_potential_keys(self, col_data: pd.Series, unique_count: int, total_count: int) -> Dict[str, Any]:
        """Analyze potential key columns."""
        key_analysis = {
            'is_potential_key': False,
            'key_type': None,
            'confidence': 0.0,
            'reasons': []
        }
        
        unique_ratio = unique_count / total_count if total_count > 0 else 0
        
        # Check for primary key characteristics
        if unique_ratio == 1.0:
            key_analysis['is_potential_key'] = True
            key_analysis['key_type'] = 'primary_key'
            key_analysis['confidence'] = 1.0
            key_analysis['reasons'].append('100% unique values')
        
        # Check for candidate key characteristics
        elif unique_ratio > 0.95:
            key_analysis['is_potential_key'] = True
            key_analysis['key_type'] = 'candidate_key'
            key_analysis['confidence'] = 0.8
            key_analysis['reasons'].append('Very high uniqueness (>95%)')
        
        # Check for natural key characteristics
        elif unique_ratio > 0.8:
            key_analysis['is_potential_key'] = True
            key_analysis['key_type'] = 'natural_key'
            key_analysis['confidence'] = 0.6
            key_analysis['reasons'].append('High uniqueness (>80%)')
        
        # Check for composite key potential
        if not key_analysis['is_potential_key'] and unique_ratio > 0.5:
            key_analysis['reasons'].append('Moderate uniqueness - potential composite key component')
        
        return key_analysis
    
    def _calculate_comprehensive_statistics(self, col_data: pd.Series, data_type: DataType) -> Dict[str, Any]:
        """Calculate comprehensive statistics for column."""
        stats = {}
        clean_data = col_data.dropna()
        
        if len(clean_data) == 0:
            return stats
        
        # Basic statistics
        stats['null_ratio'] = (len(col_data) - len(clean_data)) / len(col_data)
        stats['completeness'] = len(clean_data) / len(col_data)
        
        if data_type in [DataType.INTEGER, DataType.FLOAT]:
            # Enhanced numeric statistics
            stats.update({
                "mean": float(clean_data.mean()),
                "std": float(clean_data.std()),
                "min": float(clean_data.min()),
                "max": float(clean_data.max()),
                "median": float(clean_data.median()),
                "skewness": float(clean_data.skew()) if len(clean_data) > 2 else None,
                "kurtosis": float(clean_data.kurtosis()) if len(clean_data) > 2 else None,
                "coefficient_of_variation": float(clean_data.std() / clean_data.mean()) if clean_data.mean() != 0 else None
            })
            
            # Check for normality
            if len(clean_data) > 30:
                from scipy import stats as scipy_stats
                try:
                    _, p_value = scipy_stats.normaltest(clean_data)
                    stats['normality_test_p_value'] = float(p_value)
                    stats['is_normal'] = p_value > 0.05
                except:
                    pass
        
        elif data_type == DataType.DATETIME:
            if len(clean_data) > 0:
                stats.update({
                    "min_date": clean_data.min().isoformat(),
                    "max_date": clean_data.max().isoformat(),
                    "date_range_days": (clean_data.max() - clean_data.min()).days,
                    "date_range_years": (clean_data.max() - clean_data.min()).days / 365.25
                })
        
        elif data_type == DataType.CATEGORICAL:
            value_counts = clean_data.value_counts()
            stats.update({
                "top_values": value_counts.head(10).to_dict(),
                "entropy": self._calculate_entropy(value_counts),
                "gini_coefficient": self._calculate_gini_coefficient(value_counts),
                "simpson_diversity": self._calculate_simpson_diversity(value_counts)
            })
        
        return stats
    
    def _calculate_gini_coefficient(self, value_counts: pd.Series) -> float:
        """Calculate Gini coefficient for categorical data."""
        if len(value_counts) <= 1:
            return 0.0
        
        total = value_counts.sum()
        proportions = value_counts / total
        return float(1 - (proportions ** 2).sum())
    
    def _calculate_simpson_diversity(self, value_counts: pd.Series) -> float:
        """Calculate Simpson's diversity index."""
        if len(value_counts) <= 1:
            return 0.0
        
        total = value_counts.sum()
        proportions = value_counts / total
        return float((proportions ** 2).sum())
    
    def _get_smart_sample_values(self, col_data: pd.Series, data_type: DataType, 
                                unique_count: int, max_samples: int = 15) -> List[Any]:
        """Get smart sample values based on data type and distribution."""
        if unique_count <= max_samples:
            return col_data.dropna().unique().tolist()
        
        clean_data = col_data.dropna()
        
        if data_type in [DataType.INTEGER, DataType.FLOAT]:
            # Stratified sampling for numeric data
            percentiles = [0, 25, 50, 75, 100]
            samples = []
            for p in percentiles:
                if p == 100:
                    value = clean_data.max()
                else:
                    value = np.percentile(clean_data, p)
                samples.append(float(value))
            
            # Add some random samples
            random_samples = clean_data.sample(n=min(max_samples - len(samples), 10)).tolist()
            samples.extend(random_samples)
            
            return samples[:max_samples]
        
        elif data_type == DataType.CATEGORICAL:
            # Get top values and some random samples
            value_counts = clean_data.value_counts()
            top_values = value_counts.head(max_samples // 2).index.tolist()
            random_values = clean_data.sample(n=min(max_samples - len(top_values), max_samples // 2)).tolist()
            
            samples = top_values + random_values
            return samples[:max_samples]
        
        else:
            # Simple random sampling for other types
            return clean_data.sample(n=max_samples).tolist()
    
    def _extract_comprehensive_metadata(self, df: pd.DataFrame, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive metadata from dataset."""
        metadata = {
            **file_info,
            "processing_timestamp": datetime.now().isoformat(),
            "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024 / 1024,
            "has_duplicates": df.duplicated().any(),
            "duplicate_count": df.duplicated().sum(),
            "columns_with_nulls": df.columns[df.isnull().any()].tolist(),
            "total_null_values": df.isnull().sum().sum(),
            "null_ratio_overall": df.isnull().sum().sum() / (len(df) * len(df.columns)),
            "data_types_summary": df.dtypes.value_counts().to_dict(),
            "encoding_detection": self._detect_encoding(df),
            "estimated_memory_optimization": self._estimate_memory_optimization(df)
        }
        
        return metadata
    
    def _detect_encoding(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect potential encoding issues."""
        encoding_info = {
            'potential_issues': [],
            'recommendations': []
        }
        
        # Check for mixed data types
        mixed_types = []
        for col in df.columns:
            if df[col].dtype == 'object':
                # Check if column contains mixed types
                type_counts = df[col].apply(type).value_counts()
                if len(type_counts) > 1:
                    mixed_types.append(col)
        
        if mixed_types:
            encoding_info['potential_issues'].append(f"Mixed data types in columns: {mixed_types}")
            encoding_info['recommendations'].append("Consider data type standardization")
        
        # Check for encoding issues in string columns
        string_cols = df.select_dtypes(include=['object']).columns
        for col in string_cols:
            sample_values = df[col].dropna().head(100)
            for value in sample_values:
                if isinstance(value, str):
                    try:
                        value.encode('utf-8')
                    except UnicodeEncodeError:
                        encoding_info['potential_issues'].append(f"Encoding issues in column: {col}")
                        encoding_info['recommendations'].append("Check file encoding and consider UTF-8")
                        break
        
        return encoding_info
    
    def _estimate_memory_optimization(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Estimate memory optimization opportunities."""
        optimization = {
            'current_memory_mb': df.memory_usage(deep=True).sum() / 1024 / 1024,
            'optimized_memory_mb': 0,
            'savings_mb': 0,
            'recommendations': []
        }
        
        # Estimate optimized memory
        optimized_memory = 0
        for col in df.columns:
            col_data = df[col]
            
            if col_data.dtype == 'object':
                # String optimization
                if col_data.dtype == 'object':
                    # Check if can be converted to category
                    unique_ratio = col_data.nunique() / len(col_data)
                    if unique_ratio < 0.5:
                        optimized_memory += col_data.astype('category').memory_usage(deep=True)
                        optimization['recommendations'].append(f"Convert {col} to category (unique ratio: {unique_ratio:.2f})")
                    else:
                        optimized_memory += col_data.memory_usage(deep=True)
                else:
                    optimized_memory += col_data.memory_usage(deep=True)
            else:
                # Numeric optimization
                if col_data.dtype == 'int64':
                    if col_data.min() >= 0 and col_data.max() < 255:
                        optimized_memory += col_data.astype('uint8').memory_usage(deep=True)
                        optimization['recommendations'].append(f"Convert {col} to uint8")
                    elif col_data.min() >= -32768 and col_data.max() < 32767:
                        optimized_memory += col_data.astype('int16').memory_usage(deep=True)
                        optimization['recommendations'].append(f"Convert {col} to int16")
                    else:
                        optimized_memory += col_data.memory_usage(deep=True)
                else:
                    optimized_memory += col_data.memory_usage(deep=True)
        
        optimization['optimized_memory_mb'] = optimized_memory / 1024 / 1024
        optimization['savings_mb'] = optimization['current_memory_mb'] - optimization['optimized_memory_mb']
        
        return optimization
    
    def _get_cached_profile(self, file_path: str) -> Optional[DatasetProfile]:
        """Get cached profile if available and valid."""
        if not self.cache_dir:
            return None
        
        cache_file = self.cache_dir / f"{Path(file_path).stem}_profile.pkl"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                cache_entry: ProfileCache = pickle.load(f)
            
            # Check if cache is still valid
            current_file_info = self._get_file_info(file_path)
            
            if (cache_entry.file_hash == current_file_info['file_hash'] and
                cache_entry.file_size == current_file_info['file_size'] and
                cache_entry.file_mtime == current_file_info['file_mtime']):
                
                # Reconstruct DatasetProfile from cached data
                return DatasetProfile(**cache_entry.profile_data)
            
        except Exception as e:
            logger.warning(f"Failed to load cached profile: {e}")
        
        return None
    
    def _cache_profile(self, file_path: str, profile: DatasetProfile, file_info: Dict[str, Any]):
        """Cache profile for future use."""
        if not self.cache_dir:
            return
        
        try:
            cache_file = self.cache_dir / f"{Path(file_path).stem}_profile.pkl"
            
            cache_entry = ProfileCache(
                file_hash=file_info['file_hash'],
                profile_data=profile.dict(),
                timestamp=datetime.now(),
                file_size=file_info['file_size'],
                file_mtime=file_info['file_mtime']
            )
            
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_entry, f)
            
            logger.info(f"Profile cached to {cache_file}")
            
        except Exception as e:
            logger.warning(f"Failed to cache profile: {e}")
    
    def profile_incremental(self, file_path: str, last_profile: DatasetProfile, 
                           sample_size: int = 1000) -> Dict[str, Any]:
        """Perform incremental profiling to detect changes."""
        logger.info(f"Performing incremental profiling for {file_path}")
        
        current_profile = self.profile_dataset(file_path, sample_size, use_cache=False)
        
        changes = {
            'file_changed': False,
            'row_count_change': 0,
            'column_changes': [],
            'data_type_changes': [],
            'statistical_changes': []
        }
        
        # Check for basic changes
        if current_profile.row_count != last_profile.row_count:
            changes['file_changed'] = True
            changes['row_count_change'] = current_profile.row_count - last_profile.row_count
        
        # Check for column changes
        current_cols = {col.name: col for col in current_profile.columns}
        last_cols = {col.name: col for col in last_profile.columns}
        
        # Check for new/removed columns
        new_cols = set(current_cols.keys()) - set(last_cols.keys())
        removed_cols = set(last_cols.keys()) - set(current_cols.keys())
        
        if new_cols:
            changes['column_changes'].append(f"New columns: {list(new_cols)}")
            changes['file_changed'] = True
        
        if removed_cols:
            changes['column_changes'].append(f"Removed columns: {list(removed_cols)}")
            changes['file_changed'] = True
        
        # Check for data type changes
        for col_name in set(current_cols.keys()) & set(last_cols.keys()):
            current_col = current_cols[col_name]
            last_col = last_cols[col_name]
            
            if current_col.data_type != last_col.data_type:
                changes['data_type_changes'].append({
                    'column': col_name,
                    'old_type': last_col.data_type,
                    'new_type': current_col.data_type
                })
                changes['file_changed'] = True
        
        return changes
    
    def clear_cache(self) -> bool:
        """Clear all cached profiles."""
        if not self.cache_dir:
            return False
        
        try:
            cache_files = list(self.cache_dir.glob("*_profile.pkl"))
            for cache_file in cache_files:
                cache_file.unlink()
            
            logger.info(f"Cleared {len(cache_files)} cached profiles")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
    
    def get_profile_summary(self, profile: DatasetProfile) -> Dict[str, Any]:
        """Get a summary of the profile."""
        summary = {
            'file_path': profile.file_path,
            'row_count': profile.row_count,
            'column_count': profile.column_count,
            'total_size_mb': profile.metadata.get('memory_usage_mb', 0),
            'data_types': {},
            'null_analysis': {
                'columns_with_nulls': len(profile.metadata.get('columns_with_nulls', [])),
                'total_null_ratio': profile.metadata.get('null_ratio_overall', 0)
            },
            'key_columns': [],
            'pattern_detection': {},
            'semantic_types': {}
        }
        
        # Analyze columns
        for col in profile.columns:
            # Data type distribution
            dt = col.data_type.value
            summary['data_types'][dt] = summary['data_types'].get(dt, 0) + 1
            
            # Key analysis
            if col.statistics.get('key_analysis', {}).get('is_potential_key', False):
                summary['key_columns'].append({
                    'name': col.name,
                    'type': col.statistics['key_analysis']['key_type'],
                    'confidence': col.statistics['key_analysis']['confidence']
                })
            
            # Pattern detection
            patterns = col.statistics.get('patterns', {})
            for pattern_name, pattern_info in patterns.items():
                if pattern_name not in summary['pattern_detection']:
                    summary['pattern_detection'][pattern_name] = 0
                summary['pattern_detection'][pattern_name] += 1
            
            # Semantic types
            semantic_type = col.statistics.get('semantic_type', {}).get('primary_type')
            if semantic_type:
                if semantic_type not in summary['semantic_types']:
                    summary['semantic_types'][semantic_type] = 0
                summary['semantic_types'][semantic_type] += 1
        
        return summary
