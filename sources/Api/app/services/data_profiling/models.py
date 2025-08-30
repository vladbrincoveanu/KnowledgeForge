"""Data profiling models for column and dataset analysis."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from enum import Enum
import pandas as pd


class DataType(Enum):
    """Data type enumeration for columns."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"
    CATEGORICAL = "categorical"
    NUMERIC = "numeric"
    UNKNOWN = "unknown"


@dataclass
class ColumnProfile:
    """Profile information for a single column."""
    name: str
    data_type: DataType
    null_count: int
    unique_count: int
    sample_values: List[Any] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    # Additional profiling data
    min_value: Optional[Union[str, int, float]] = None
    max_value: Optional[Union[str, int, float]] = None
    mean_value: Optional[float] = None
    std_value: Optional[float] = None
    median_value: Optional[float] = None
    
    # Pattern detection
    patterns: List[str] = field(default_factory=list)
    semantic_type: Optional[str] = None
    
    # Quality metrics
    completeness: float = 0.0
    uniqueness: float = 0.0
    consistency: float = 0.0
    
    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        if self.unique_count > 0 and hasattr(self, 'total_count'):
            self.uniqueness = self.unique_count / self.total_count if hasattr(self, 'total_count') else 0.0


@dataclass
class DatasetProfile:
    """Complete profile of a dataset."""
    file_path: str
    file_size: int
    row_count: int
    column_count: int
    columns: List[ColumnProfile] = field(default_factory=list)
    
    # Dataset-level statistics
    total_cells: int = 0
    missing_cells: int = 0
    duplicate_rows: int = 0
    
    # Quality scores
    overall_quality_score: float = 0.0
    data_completeness: float = 0.0
    data_consistency: float = 0.0
    
    # Metadata
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    checksum: Optional[str] = None
    
    # Profiling metadata
    profiling_time: float = 0.0
    sample_size: int = 0
    
    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        self.total_cells = self.row_count * self.column_count
        if self.total_cells > 0:
            self.data_completeness = (self.total_cells - self.missing_cells) / self.total_cells
    
    def get_column_profile(self, column_name: str) -> Optional[ColumnProfile]:
        """Get profile for a specific column."""
        for col in self.columns:
            if col.name == column_name:
                return col
        return None
    
    def get_quality_summary(self) -> Dict[str, Any]:
        """Get a summary of dataset quality metrics."""
        return {
            "overall_quality": self.overall_quality_score,
            "completeness": self.data_completeness,
            "consistency": self.data_consistency,
            "missing_data": self.missing_cells,
            "duplicate_rows": self.duplicate_rows,
            "column_count": self.column_count,
            "row_count": self.row_count
        }


@dataclass
class ProfileCache:
    """Cache entry for dataset profiles."""
    file_hash: str
    profile_data: Dict[str, Any]
    timestamp: str
    file_size: int
    file_mtime: float
    profiling_time: float = 0.0


@dataclass
class QualityRule:
    """Data quality rule definition."""
    rule_id: str
    rule_name: str
    rule_type: str  # 'threshold', 'pattern', 'completeness', 'consistency'
    field: str
    condition: str
    threshold: Optional[float] = None
    severity: str = 'warning'  # 'info', 'warning', 'error', 'critical'
    description: str = ""


@dataclass
class QualityResult:
    """Result of quality rule evaluation."""
    rule_id: str
    rule_name: str
    field: str
    passed: bool
    actual_value: Any
    expected_value: Any
    message: str
    severity: str = 'warning'
    timestamp: str = ""


def infer_data_type(series: pd.Series) -> DataType:
    """Infer the data type of a pandas series."""
    if series.dtype == 'object':
        # Check for datetime patterns
        if series.str.match(r'^\d{4}-\d{2}-\d{2}').any():
            return DataType.DATE
        elif series.str.match(r'^\d{2}:\d{2}').any():
            return DataType.TIME
        elif series.str.match(r'^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}').any():
            return DataType.DATETIME
        elif series.nunique() / len(series) < 0.5:  # Low cardinality
            return DataType.CATEGORICAL
        else:
            return DataType.STRING
    elif series.dtype == 'int64':
        return DataType.INTEGER
    elif series.dtype == 'float64':
        return DataType.FLOAT
    elif series.dtype == 'bool':
        return DataType.BOLEAN
    else:
        return DataType.UNKNOWN


def calculate_column_statistics(series: pd.Series, data_type: DataType) -> Dict[str, Any]:
    """Calculate statistics for a column based on its data type."""
    stats = {}
    
    if data_type in [DataType.INTEGER, DataType.FLOAT]:
        stats['min'] = series.min()
        stats['max'] = series.max()
        stats['mean'] = series.mean()
        stats['std'] = series.std()
        stats['median'] = series.median()
        stats['q25'] = series.quantile(0.25)
        stats['q75'] = series.quantile(0.75)
    elif data_type == DataType.CATEGORICAL:
        stats['unique_values'] = series.nunique()
        stats['most_common'] = series.mode().iloc[0] if not series.mode().empty else None
        stats['least_common'] = series.value_counts().index[-1] if len(series.value_counts()) > 0 else None
    elif data_type == DataType.STRING:
        stats['min_length'] = series.str.len().min()
        stats['max_length'] = series.str.len().max()
        stats['avg_length'] = series.str.len().mean()
    
    return stats
