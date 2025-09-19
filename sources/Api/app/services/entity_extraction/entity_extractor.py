from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, TypedDict
from enum import Enum

import numpy as np
import pandas as pd

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    from langgraph.graph.graph import CompiledGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logging.warning("LangGraph not available. Install with: pip install langgraph")

# Import your local models
from app.domain.models.entities import ColumnProfile, DataType, Entity, Attribute, infer_entity_name

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# -----------------------
# Entity Type Taxonomy
# -----------------------
class EntityType(Enum):
    """Defined taxonomy of entity types with hierarchy."""
    TABLE = "table"
    IDENTIFIER = "identifier"
    MEASUREMENT = "measurement"
    TEMPORAL = "temporal"
    GEOGRAPHIC = "geographic"
    CONTACT = "contact"
    CATEGORICAL = "categorical"
    BUSINESS = "business"
    COMPOSITE = "composite"
    UNKNOWN = "unknown"
    
    # Subtypes
    UUID = "identifier.uuid"
    SEQUENTIAL_ID = "identifier.sequential"
    FOREIGN_KEY = "identifier.foreign_key"
    PRIMARY_KEY = "identifier.primary"
    
    PERCENTAGE = "measurement.percentage"
    CURRENCY = "measurement.currency"
    QUANTITY = "measurement.quantity"
    DIMENSION = "measurement.dimension"
    
    DATE = "temporal.date"
    TIME = "temporal.time"
    DATETIME = "temporal.datetime"
    YEAR = "temporal.year"
    MONTH = "temporal.month"
    
    LATITUDE = "geographic.latitude"
    LONGITUDE = "geographic.longitude"
    ADDRESS = "geographic.address"
    POSTAL_CODE = "geographic.postal_code"
    COUNTRY = "geographic.country"
    REGION = "geographic.region"
    CITY = "geographic.city"
    
    EMAIL = "contact.email"
    PHONE = "contact.phone"
    URL = "contact.url"
    IP_ADDRESS = "contact.ip_address"
    
    STATUS = "categorical.status"
    TYPE = "categorical.type"
    CATEGORY = "categorical.category"
    CLASSIFICATION = "categorical.classification"

# -----------------------
# LangGraph State Definition
# -----------------------
class ExtractionState(TypedDict):
    """State for the entity extraction workflow."""
    # Input data
    file_path: str
    columns: List[ColumnProfile]
    config: Dict[str, Any]
    df: Optional[pd.DataFrame]
    
    # Analysis results
    dataset_type: Optional[str]  # "table_level", "time_series", "relational", "column_level"
    dataset_context: Dict[str, Any]
    entity_name: Optional[str]
    domain: Optional[str]
    
    # Extraction results
    entities: List[Entity]
    confidence_scores: Dict[str, float]
    
    # Workflow control
    extraction_strategy: Optional[str]
    should_use_llm: bool
    needs_consolidation: bool
    error: Optional[str]

# -----------------------
# Utility: Regex patterns
# -----------------------
_REG_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_REG_URL = re.compile(r"^(https?://)?([a-zA-Z][\w-]*\.)+[\w-]+(/\S*)?$")
_REG_IP = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
_REG_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
_REG_HEXISH_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_REG_CREDIT_CARD = re.compile(r"^(?:\d[ -]*?){13,19}$")
_REG_PHONE = re.compile(r"^\+?[0-9 .()\-]{7,}$")
_REG_POSTAL_5 = re.compile(r"^\d{5}$")  # US-like; adjust by region if needed
_REG_PERCENT = re.compile(r"^-?\d{1,3}(?:\.\d+)?%$")
_REG_LAT = re.compile(r"^[+-]?(?:90(?:\.0+)?|[0-8]?\d(?:\.\d+)?)$")
_REG_LON = re.compile(r"^[+-]?(?:180(?:\.0+)?|1[0-7]\d(?:\.\d+)?|\d?\d(?:\.\d+)?)$")
_REG_YEAR = re.compile(r"^(19\d{2}|20\d{2}|2100)$")
_REG_CURRENCY = re.compile(r"^\$?\d+(?:,\d{3})*(?:\.\d{2})?$")

# -----------------------------------------------------
# Helpers: deterministic hashing & JSON-safe operations
# -----------------------------------------------------
def _stable_hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _hash_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

# ---------------------------------------
# Main Extractor with table-level focus
# ---------------------------------------
def _safe_config_get(config, key, default=None):
    """Safely get configuration value from either dict or Config object."""
    if hasattr(config, 'get'):
        return config.get(key, default)
    elif hasattr(config, key):
        return getattr(config, key, default)
    elif hasattr(config, 'extraction') and hasattr(config.extraction, key):
        return getattr(config.extraction, key, default)
    else:
        return default

class LangGraphEntityExtractor:
    """LangGraph-based entity extractor with graph workflow."""
    
    def __init__(
        self,
        cache_dir: str | Path | None = ".cache/entity_extractor",
        llm_manager: Any | None = None,
        embeddings_manager: Any | None = None,
    ) -> None:
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("LangGraph is required for this extractor. Install with: pip install langgraph")
            
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.llm_cache_dir = self.cache_dir / "llm"
            self.llm_cache_dir.mkdir(parents=True, exist_ok=True)
            
        self.llm_manager = llm_manager
        self.embeddings = embeddings_manager
        
        # Initialize the extraction graph
        self.graph = self._build_extraction_graph()
        
        # Domain patterns and configurations
        self.domain_patterns = self._load_domain_patterns()
        self.entity_priority = self._get_entity_priority()
        self.confidence_thresholds = {
            "rule_based": 0.9,
            "pattern_based": 0.8,
            "llm_structured": 0.7,
            "llm_general": 0.5,
            "fallback": 0.3
        }

    def _build_extraction_graph(self) -> CompiledGraph:
        """Build the LangGraph workflow for entity extraction."""
        workflow = StateGraph(ExtractionState)
        
        # Add nodes for different processing steps
        workflow.add_node("analyze_dataset", self._analyze_dataset_node)
        workflow.add_node("load_data", self._load_data_node)
        workflow.add_node("extract_table_level", self._extract_table_level_node)
        workflow.add_node("extract_time_series", self._extract_time_series_node)
        workflow.add_node("extract_relational", self._extract_relational_node)
        workflow.add_node("extract_column_level", self._extract_column_level_node)
        workflow.add_node("llm_enhance", self._llm_enhance_node)
        workflow.add_node("consolidate", self._consolidate_node)
        
        # Set entry point
        workflow.set_entry_point("load_data")
        
        # Add conditional edges for routing
        workflow.add_edge("load_data", "analyze_dataset")
        
        workflow.add_conditional_edges(
            "analyze_dataset",
            self._route_extraction_strategy,
            {
                "table_level": "extract_table_level",
                "time_series": "extract_time_series", 
                "relational": "extract_relational",
                "column_level": "extract_column_level"
            }
        )
        
        # All extraction strategies go to consolidate
        workflow.add_edge("extract_table_level", "consolidate")
        workflow.add_edge("extract_time_series", "consolidate")
        workflow.add_edge("extract_relational", "consolidate")
        workflow.add_edge("extract_column_level", "consolidate")
        
        # Conditional edge from consolidate
        workflow.add_conditional_edges(
            "consolidate",
            self._should_enhance_with_llm,
            {
                "enhance": "llm_enhance",
                "finish": END
            }
        )
        
        workflow.add_edge("llm_enhance", END)
        
        return workflow.compile()

    def extract_entities(
        self,
        file_path: str,
        columns: List[ColumnProfile],
        config: Dict[str, Any],
    ) -> List[Entity]:
        """Main entry point using LangGraph workflow."""
        logger.info(f"Extracting entities from {file_path} using LangGraph workflow")

        # Check cache first
        file_hash = _hash_file(file_path)
        cached = self._load_cached_entities(file_hash)
        if cached is not None:
            logger.info("Returning cached entities")
            return cached

        # Initialize state
        initial_state: ExtractionState = {
            "file_path": file_path,
            "columns": columns,
            "config": config,
            "df": None,
            "dataset_type": None,
            "dataset_context": {},
            "entity_name": None,
            "domain": None,
            "entities": [],
            "confidence_scores": {},
            "extraction_strategy": None,
            "should_use_llm": _safe_config_get(config, "use_llm", True),
            "needs_consolidation": True,
            "error": None
        }

        try:
            # Run the graph workflow
            final_state = self.graph.invoke(initial_state)
            
            if final_state.get("error"):
                logger.error(f"Extraction failed: {final_state['error']}")
                return []
            
            entities = final_state.get("entities", [])
            
            # Cache the results
            try:
                self._save_cached_entities(file_hash, entities)
            except Exception as e:
                logger.warning(f"Failed to save cache: {e}")
            
            logger.info(f"LangGraph extraction completed: {len(entities)} entities")
            return entities
            
        except Exception as e:
            logger.error(f"LangGraph extraction failed: {e}")
            # Fallback to traditional extraction
            logger.info("Falling back to traditional extraction")
            fallback_extractor = EntityExtractor(
                cache_dir=self.cache_dir,
                llm_manager=self.llm_manager,
                embeddings_manager=self.embeddings
            )
            return fallback_extractor.extract_entities(file_path, columns, config)

    # Graph node implementations
    def _load_data_node(self, state: ExtractionState) -> ExtractionState:
        """Load and prepare data for analysis."""
        try:
            df = self._safe_read_csv(state["file_path"], usecols=[c.name for c in state["columns"]])
            state["df"] = df
            logger.info(f"Loaded data: {df.shape}")
        except Exception as e:
            state["error"] = f"Failed to load data: {e}"
            logger.error(state["error"])
        return state

    def _analyze_dataset_node(self, state: ExtractionState) -> ExtractionState:
        """Analyze dataset to determine extraction strategy."""
        try:
            columns = state["columns"]
            df = state["df"]
            
            # Analyze dataset context
            dataset_context = self._analyze_dataset_context(df, columns, state["file_path"])
            state["dataset_context"] = dataset_context
            state["domain"] = dataset_context.get("domain_context", "generic")
            
            # Determine dataset type and strategy
            if self._is_multi_entity_dataset(columns):
                if self._is_time_series_dataset(columns):
                    state["dataset_type"] = "time_series"
                    state["extraction_strategy"] = "time_series"
                else:
                    state["dataset_type"] = "relational"
                    state["extraction_strategy"] = "relational"
            else:
                # Try table-level first
                entity_name = self._infer_meaningful_entity_name(state["file_path"], columns, state["config"])
                if entity_name not in ['Entity', 'Record']:
                    state["dataset_type"] = "table_level"
                    state["extraction_strategy"] = "table_level"
                    state["entity_name"] = entity_name
                else:
                    state["dataset_type"] = "column_level"
                    state["extraction_strategy"] = "column_level"
            
            logger.info(f"Determined strategy: {state['extraction_strategy']}")
            
        except Exception as e:
            state["error"] = f"Dataset analysis failed: {e}"
            logger.error(state["error"])
        
        return state

    def _route_extraction_strategy(self, state: ExtractionState) -> str:
        """Route to appropriate extraction strategy."""
        return state.get("extraction_strategy", "column_level")

    def _extract_table_level_node(self, state: ExtractionState) -> ExtractionState:
        """Extract table-level entities."""
        try:
            columns = state["columns"]
            entity_name = state.get("entity_name", "Entity")
            
            # Create attributes from all columns
            attributes = []
            for column in columns:
                attribute = Attribute(
                    name=column.name,
                    data_type=column.data_type,
                    source_column=column.name,
                    confidence=0.95,
                    statistics=column.statistics,
                    sample_values=column.sample_values
                )
                attributes.append(attribute)
            
            # Determine entity type
            entity_type = self._determine_entity_type(entity_name, columns)
            
            # Create the main entity
            entity = Entity(
                id=str(uuid.uuid4()),
                name=entity_name,
                entity_type=entity_type,
                attributes=attributes,
                confidence=1.0,
                source_table=state["file_path"]
            )
            
            state["entities"] = [entity]
            state["confidence_scores"]["table_level"] = 1.0
            
            logger.info(f"Created table-level entity: {entity_name} ({entity_type})")
            
        except Exception as e:
            state["error"] = f"Table-level extraction failed: {e}"
            logger.error(state["error"])
        
        return state

    def _extract_time_series_node(self, state: ExtractionState) -> ExtractionState:
        """Extract entities from time-series data."""
        try:
            columns = state["columns"]
            df = state["df"]
            entities = self._extract_time_series_entities(df, columns, state["config"], state["dataset_context"])
            
            state["entities"] = entities
            state["confidence_scores"]["time_series"] = 0.95
            
            logger.info(f"Extracted {len(entities)} time-series entities")
            
        except Exception as e:
            state["error"] = f"Time-series extraction failed: {e}"
            logger.error(state["error"])
        
        return state

    def _extract_relational_node(self, state: ExtractionState) -> ExtractionState:
        """Extract entities from relational data."""
        try:
            columns = state["columns"]
            df = state["df"]
            entities = self._extract_relational_entities(df, columns, state["config"], state["dataset_context"])
            
            state["entities"] = entities
            state["confidence_scores"]["relational"] = 0.85
            
            logger.info(f"Extracted {len(entities)} relational entities")
            
        except Exception as e:
            state["error"] = f"Relational extraction failed: {e}"
            logger.error(state["error"])
        
        return state

    def _extract_column_level_node(self, state: ExtractionState) -> ExtractionState:
        """Extract entities at column level (fallback)."""
        try:
            columns = state["columns"]
            df = state["df"]
            entities = self._extract_column_level_entities(df, columns, state["config"])
            
            state["entities"] = entities
            state["confidence_scores"]["column_level"] = 0.7
            
            logger.info(f"Extracted {len(entities)} column-level entities")
            
        except Exception as e:
            state["error"] = f"Column-level extraction failed: {e}"
            logger.error(state["error"])
        
        return state

    def _consolidate_node(self, state: ExtractionState) -> ExtractionState:
        """Consolidate and filter entities."""
        try:
            entities = state["entities"]
            config = state["config"]
            
            # Apply confidence threshold
            confidence_threshold = float(_safe_config_get(config, "confidence_threshold", 0.70))
            entities = [e for e in entities if float(getattr(e, "confidence", 1.0)) >= confidence_threshold]
            
            # Apply max entities limit
            max_entities = int(_safe_config_get(config, "max_entities", 100_000))
            if len(entities) > max_entities:
                entities = entities[:max_entities]
            
            # Deduplicate if requested
            if _safe_config_get(config, "use_intelligent_consolidation", True):
                entities = self._deduplicate_by_embeddings(entities, config)
            
            state["entities"] = entities
            logger.info(f"Consolidated to {len(entities)} entities")
            
        except Exception as e:
            state["error"] = f"Consolidation failed: {e}"
            logger.error(state["error"])
        
        return state

    def _should_enhance_with_llm(self, state: ExtractionState) -> str:
        """Determine if LLM enhancement is needed."""
        config = state["config"]
        should_use_llm = state["should_use_llm"]
        
        # Check if business entity extraction is enabled
        extract_business = _safe_config_get(config, "extract_business_entities", False)
        
        if should_use_llm and extract_business and self.llm_manager:
            return "enhance"
        return "finish"

    def _llm_enhance_node(self, state: ExtractionState) -> ExtractionState:
        """Enhance entities using LLM."""
        try:
            df = state["df"]
            columns = state["columns"]
            config = state["config"]
            existing_entities = state["entities"]
            
            # Extract business entities using LLM
            business_entities = self._extract_business_entities_llm(df, columns, config)
            
            # Combine with existing entities
            all_entities = existing_entities + business_entities
            
            # Deduplicate again if needed
            if _safe_config_get(config, "use_intelligent_consolidation", True):
                all_entities = self._deduplicate_by_embeddings(all_entities, config)
            
            state["entities"] = all_entities
            logger.info(f"LLM enhanced to {len(all_entities)} entities")
            
        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")
            # Continue with existing entities
        
        return state

    # Utility methods (reuse from original EntityExtractor)
    def _load_domain_patterns(self) -> Dict[str, Dict[str, List[str]]]:
        """Load domain-specific patterns for better entity recognition."""
        return {
            "healthcare": {
                "business_entities": ["patient", "doctor", "hospital", "treatment", "diagnosis"],
                "measurement": ["probability", "score", "risk", "rate", "level"],
                "categorical": ["status", "type", "category", "outcome", "result"],
                "identifier": ["id", "patient_id", "record_id", "case_id"]
            },
            "finance": {
                "measurement": ["revenue", "profit", "expense", "asset", "liability", "equity"],
                "categorical": ["account_type", "transaction_type", "sector", "industry"],
                "temporal": ["fiscal_year", "quarter", "reporting_date"]
            },
        }

    def _get_entity_priority(self) -> List[str]:
        """Define priority order for entity types."""
        return [
            "contact.email", "contact.url", "contact.ip_address", "contact.phone",
            "identifier.uuid", "identifier.sequential", "geographic.latitude", "geographic.longitude",
            "geographic.postal_code", "temporal.date", "temporal.time", "temporal.datetime",
            "measurement.percentage", "measurement.currency", "identifier.primary",
            "identifier.foreign_key", "identifier.identifier", "measurement.quantity",
            "measurement.dimension", "geographic.country", "geographic.region",
            "geographic.city", "geographic.address", "temporal.year", "temporal.month",
            "categorical.status", "categorical.type", "categorical.category",
            "categorical.classification", "business.patient", "business.business",
            "measurement.measurement", "categorical.categorical", "unknown"
        ]

    # Cache methods
    def _cache_path(self, key: str, suffix: str = ".json") -> Path | None:
        if not self.cache_dir:
            return None
        p = self.cache_dir / f"{key}{suffix}"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load_cached_entities(self, file_hash: str) -> List[Entity] | None:
        path = self._cache_path(file_hash)
        if path and path.exists():
            try:
                data = json.loads(path.read_text())
                return [Entity(**e) for e in data]
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")
        return None

    def _save_cached_entities(self, file_hash: str, entities: List[Entity]) -> None:
        path = self._cache_path(file_hash)
        if not path:
            return
        payload = [e.model_dump() for e in entities]
        path.write_text(json.dumps(payload, ensure_ascii=False))

    @staticmethod
    def _safe_read_csv(path: str | Path, usecols: List[str] | None = None) -> pd.DataFrame:
        return pd.read_csv(path, usecols=usecols, low_memory=False)

    # Methods imported from original EntityExtractor (will be copied over)
    def _is_multi_entity_dataset(self, columns: List[ColumnProfile]) -> bool:
        """Check if the dataset contains multiple entity types."""
        if not columns:
            return False
        
        entity_keywords = ['country', 'region', 'state', 'city', 'product', 'customer', 
                          'supplier', 'employee', 'department', 'category', 'group',
                          'company', 'organization', 'location', 'branch', 'store',
                          'patient', 'user', 'account', 'order', 'transaction', 'address']
        
        entity_types_found = set()
        
        for col in columns:
            col_name_lower = col.name.lower()
            
            for keyword in entity_keywords:
                if keyword in col_name_lower:
                    entity_types_found.add(keyword)
            
            if '_id' in col_name_lower and col.data_type in [DataType.STRING, DataType.INTEGER]:
                entity_type = col_name_lower.replace('_id', '')
                if entity_type in entity_keywords:
                    entity_types_found.add(entity_type)
        
        return len(entity_types_found) >= 1

    def _is_time_series_dataset(self, columns: List[ColumnProfile]) -> bool:
        """Check if the dataset represents time-series data."""
        year_columns = 0
        for col in columns:
            col_name = str(col.name)
            if col_name.isdigit() and len(col_name) == 4:
                year = int(col_name)
                if 1900 <= year <= 2100:
                    year_columns += 1
            elif any(pattern in col_name.lower() for pattern in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                                                                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
                                                                  'q1', 'q2', 'q3', 'q4', 'quarter']):
                year_columns += 1
        
        return year_columns > len(columns) * 0.3

    def _infer_meaningful_entity_name(self, file_path: str, columns: List[ColumnProfile], config: Dict[str, Any] = None) -> str:
        """Infer a semantically meaningful entity name."""
        from pathlib import Path
        import re
        
        # Get base filename without extension
        filename = Path(file_path).stem.lower()
        original_filename = filename
        
        # Clean up common prefixes/suffixes
        cleanup_patterns = ['sample_', 'test_', 'demo_', 'temp_', 'tmp_', 'export_', 'import_', 
                           '_data', '_dataset', '_table', '_csv', '_export', '_import', '_file']
        for pattern in cleanup_patterns:
            filename = filename.replace(pattern, '')
        
        # Remove numbers and top patterns
        filename = re.sub(r'^\d+_|_\d+$', '', filename)
        filename = re.sub(r'^top_\d+_', '', filename)
        
        parts = re.split(r'[_\-]', filename)
        noise_words = ['of', 'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 
                       'from', 'about', 'all', 'new', 'old', 'top', 'high', 'low', 'risk',
                       'list', 'data', 'info', 'information', 'details', 'records']
        
        meaningful_parts = [p for p in parts if p and p not in noise_words]
        
        if meaningful_parts:
            last_part = meaningful_parts[-1]
            if last_part.endswith('ies'):
                return last_part[:-3] + 'y'
            elif last_part.endswith('es'):
                return last_part[:-2]
            elif last_part.endswith('s') and len(last_part) > 3:
                return last_part[:-1]
            elif len(last_part) > 2:
                return last_part.capitalize()
        
        return 'Entity'

    def _determine_entity_type(self, entity_name: str, columns: List[ColumnProfile] = None) -> str:
        """Determine the appropriate entity type."""
        entity_name_lower = entity_name.lower()
        
        if any(word in entity_name_lower for word in ['country', 'region', 'state', 'city', 'location']):
            return EntityType.GEOGRAPHIC.value
        elif any(word in entity_name_lower for word in ['measurement', 'metric', 'score', 'rate', 'percentage']):
            return EntityType.MEASUREMENT.value
        elif any(word in entity_name_lower for word in ['date', 'time', 'period', 'duration']):
            return EntityType.TEMPORAL.value
        else:
            return EntityType.BUSINESS.value

    def _analyze_dataset_context(self, df: pd.DataFrame, columns: List[ColumnProfile], file_path: str = None) -> Dict[str, Any]:
        """Analyze the dataset to understand its business context."""
        context = {
            "has_geographic_data": False,
            "has_time_series": False,
            "has_percentage_data": False,
            "has_financial_data": False,
            "primary_measurement_type": "generic",
            "column_patterns": {},
            "domain_context": "generic",
            "measurement_context": "generic"
        }
        
        # Extract insights from filename if available
        if file_path:
            filename_insights = self._extract_filename_insights(file_path)
            context.update(filename_insights)
        
        # Check for geographic columns
        geo_keywords = ['country', 'region', 'state', 'city', 'location', 'geo', 'area']
        for col in columns:
            col_lower = col.name.lower()
            if any(keyword in col_lower for keyword in geo_keywords):
                context["has_geographic_data"] = True
                context["column_patterns"][col.name] = "geographic"
        
        # Check for time series
        year_cols = [col for col in columns if self._is_time_column(col.name)]
        if len(year_cols) > 3:
            context["has_time_series"] = True
        
        # Check data values for percentages
        for col in columns:
            if col.data_type in [DataType.FLOAT, DataType.NUMERICAL]:
                sample_vals = df[col.name].dropna().head(100)
                if len(sample_vals) > 0:
                    if (sample_vals >= 0).all() and (sample_vals <= 100).all():
                        context["has_percentage_data"] = True
                        break
        
        # Check for financial data
        financial_keywords = ['price', 'cost', 'revenue', 'profit', 'salary', 'expense']
        for col in columns:
            col_lower = col.name.lower()
            if any(keyword in col_lower for keyword in financial_keywords):
                context["has_financial_data"] = True
                break
        
        return context

    def _extract_filename_insights(self, file_path: str) -> Dict[str, Any]:
        """Extract semantic insights from the filename."""
        from pathlib import Path
        
        filename = Path(file_path).stem.lower()
        insights = {
            "domain_context": "generic",
            "measurement_context": "generic",
        }
        
        domain_patterns = {
            "healthcare": ["patient", "medical", "health", "hospital", "readmission"],
            "finance": ["finance", "financial", "revenue", "profit", "investment"],
            "education": ["education", "school", "student", "academic", "university"],
            "retail": ["retail", "sales", "customer", "product", "inventory"],
        }
        
        for domain, keywords in domain_patterns.items():
            if any(keyword in filename for keyword in keywords):
                insights["domain_context"] = domain
                break
        
        return insights

    def _is_time_column(self, col_name: str) -> bool:
        """Check if a column name represents a time dimension."""
        if col_name.isdigit() and len(col_name) == 4:
            year = int(col_name)
            return 1900 <= year <= 2100
        
        time_keywords = ['year', 'month', 'date', 'time', 'quarter', 'period']
        return any(keyword in col_name.lower() for keyword in time_keywords)

    def _extract_time_series_entities(self, df: pd.DataFrame, columns: List[ColumnProfile], config: Dict[str, Any], dataset_context: Dict[str, Any]) -> List[Entity]:
        """Extract entities from time-series multi-entity datasets."""
        entities: List[Entity] = []
        first_col = columns[0]
        
        if first_col.data_type == DataType.STRING:
            entity_name = self._infer_meaningful_entity_name("", columns, config)
            entity_type = self._determine_entity_type(entity_name, columns)
            
            attribute = Attribute(
                name=first_col.name,
                data_type=first_col.data_type,
                source_column=first_col.name,
                confidence=0.95,
                statistics=first_col.statistics,
                sample_values=first_col.sample_values
            )
            
            entity = Entity(
                name=entity_name,
                entity_type=entity_type,
                attributes=[attribute],
                confidence=0.95,
                source_table=""
            )
            entity.id = str(uuid.uuid4())
            entities.append(entity)
            
        return entities

    def _extract_relational_entities(self, df: pd.DataFrame, columns: List[ColumnProfile], config: Dict[str, Any], dataset_context: Dict[str, Any]) -> List[Entity]:
        """Extract entities from relational multi-entity datasets."""
        entities: List[Entity] = []
        
        # Simple implementation for now
        for col in columns[:5]:  # Limit to first 5 columns
            attribute = Attribute(
                name=col.name,
                data_type=col.data_type,
                source_column=col.name,
                confidence=0.8,
                statistics=col.statistics,
                sample_values=col.sample_values
            )
            
            entity = Entity(
                name=col.name.capitalize(),
                entity_type=EntityType.CATEGORICAL.value,
                attributes=[attribute],
                confidence=0.8,
                source_table=""
            )
            entity.id = str(uuid.uuid4())
            entities.append(entity)
            
        return entities

    def _extract_column_level_entities(self, df: pd.DataFrame, columns: List[ColumnProfile], config: Dict[str, Any]) -> List[Entity]:
        """Extract entities at the column level as fallback."""
        entities: List[Entity] = []
        
        for col in columns[:10]:  # Limit for now
            attribute = Attribute(
                name=col.name,
                data_type=col.data_type,
                source_column=col.name,
                confidence=0.7,
                statistics=col.statistics,
                sample_values=col.sample_values
            )
            
            entity = Entity(
                name=col.name,
                entity_type=EntityType.CATEGORICAL.value,
                attributes=[attribute],
                confidence=0.7,
                source_table=""
            )
            entity.id = str(uuid.uuid4())
            entities.append(entity)
            
        return entities

    def _extract_business_entities_llm(self, df: pd.DataFrame, columns: List[ColumnProfile], config: Dict[str, Any]) -> List[Entity]:
        """Extract business entities using LLM."""
        # Simplified implementation
        return []

    def _deduplicate_by_embeddings(self, entities: List[Entity], config: Dict[str, Any]) -> List[Entity]:
        """Deduplicate entities by embeddings or simple text matching."""
        if not entities:
            return entities
            
        # Simple text-based deduplication for now
        seen = set()
        out: List[Entity] = []
        for e in entities:
            sig = (e.name, e.entity_type)
            if sig in seen:
                continue
            seen.add(sig)
            out.append(e)
        return out


class EntityExtractor:
    def __init__(
        self,
        cache_dir: str | Path | None = ".cache/entity_extractor",
        llm_manager: Any | None = None,
        embeddings_manager: Any | None = None,
        use_langgraph: bool = True,
    ) -> None:
        # Check if we should use LangGraph
        self.use_langgraph = use_langgraph and LANGGRAPH_AVAILABLE
        self._langgraph_extractor = None
        
        if self.use_langgraph:
            try:
                self._langgraph_extractor = LangGraphEntityExtractor(
                    cache_dir=cache_dir,
                    llm_manager=llm_manager,
                    embeddings_manager=embeddings_manager
                )
                logger.info("Using LangGraph-based entity extraction")
            except Exception as e:
                logger.warning(f"Failed to initialize LangGraph extractor, falling back to traditional: {e}")
                self.use_langgraph = False
        
        # Traditional extractor setup
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Create separate cache for LLM results
            self.llm_cache_dir = self.cache_dir / "llm"
            self.llm_cache_dir.mkdir(parents=True, exist_ok=True)
        self.llm_manager = llm_manager
        self.embeddings = embeddings_manager
        
        # Domain-specific patterns (will be dynamically extended via LLM)
        self.domain_patterns = self._load_domain_patterns()
        
        # Entity priority for selection
        self.entity_priority = self._get_entity_priority()
        
        # LLM extraction confidence thresholds
        self.confidence_thresholds = {
            "rule_based": 0.9,
            "pattern_based": 0.8,
            "llm_structured": 0.7,
            "llm_general": 0.5,
            "fallback": 0.3
        }

    def _load_domain_patterns(self) -> Dict[str, Dict[str, List[str]]]:
        """Load domain-specific patterns for better entity recognition."""
        return {
            "healthcare": {
                "business_entities": ["patient", "doctor", "hospital", "treatment", "diagnosis"],
                "measurement": ["probability", "score", "risk", "rate", "level"],
                "categorical": ["status", "type", "category", "outcome", "result"],
                "identifier": ["id", "patient_id", "record_id", "case_id"]
            },
            "finance": {
                "measurement": ["revenue", "profit", "expense", "asset", "liability", "equity"],
                "categorical": ["account_type", "transaction_type", "sector", "industry"],
                "temporal": ["fiscal_year", "quarter", "reporting_date"]
            },
            # Add more domains as needed
        }

    def _get_entity_priority(self) -> List[str]:
        """Define priority order for entity types when selecting the best one."""
        return [
            "contact.email",
            "contact.url",
            "contact.ip_address",
            "contact.phone",
            "identifier.uuid",
            "identifier.sequential",
            "geographic.latitude",
            "geographic.longitude",
            "geographic.postal_code",
            "temporal.date",
            "temporal.time",
            "temporal.datetime",
            "measurement.percentage",
            "measurement.currency",
            "identifier.primary",
            "identifier.foreign_key",
            "identifier.identifier",
            "measurement.quantity",
            "measurement.dimension",
            "geographic.country",
            "geographic.region",
            "geographic.city",
            "geographic.address",
            "temporal.year",
            "temporal.month",
            "categorical.status",
            "categorical.type",
            "categorical.category",
            "categorical.classification",
            "business.patient",
            "business.business",
            "measurement.measurement",
            "categorical.categorical",
            "unknown"
        ]

    def _generate_entity_id(self, entity: Entity) -> str:
        """Generate a deterministic ID for an entity based on its content."""
        # Create a stable hash based on entity properties
        content = f"{entity.name}_{entity.entity_type}_{entity.source_table}"
        return f"entity_{_stable_hash_text(content)[:12]}"
    
    # ---------- LLM-based extraction methods ----------
    def _llm_cache_key(self, operation: str, content: str) -> str:
        """Generate cache key for LLM operations."""
        return f"{operation}_{_stable_hash_text(content)[:16]}"
    
    def _get_llm_cached(self, cache_key: str) -> Any | None:
        """Get cached LLM result."""
        if not self.llm_cache_dir:
            return None
        cache_file = self.llm_cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except Exception as e:
                logger.debug(f"Cache read failed for {cache_key}: {e}")
        return None
    
    def _save_llm_cache(self, cache_key: str, result: Any) -> None:
        """Save LLM result to cache."""
        if not self.llm_cache_dir:
            return
        cache_file = self.llm_cache_dir / f"{cache_key}.json"
        try:
            cache_file.write_text(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"Cache save failed for {cache_key}: {e}")
    
    def _llm_infer_entity_name(self, filename: str, columns: list[ColumnProfile], sample_data: dict = None) -> tuple[str, float]:
        """Use LLM to infer what each row represents in the dataset."""
        if not self.llm_manager:
            return "Entity", 0.3
        
        # Check cache first
        cache_content = f"{filename}_{[c.name for c in columns[:10]]}"  # Use first 10 columns for cache
        cache_key = self._llm_cache_key("entity_name", cache_content)
        
        if cached := self._get_llm_cached(cache_key):
            return cached["name"], cached["confidence"]
        
        # Prepare column info
        column_info = []
        for col in columns[:10]:  # Limit to first 10 columns for context
            col_info = f"- {col.name} ({col.data_type.value})"
            if col.sample_values and len(col.sample_values) > 0:
                samples = str(col.sample_values[:3])
                col_info += f" samples: {samples}"
            column_info.append(col_info)
        
        prompt = f"""Analyze this dataset and determine what each row represents.

Dataset: {filename}
Columns:
{chr(10).join(column_info)}

Based on the filename and column structure, what does each row in this dataset represent?

Return a JSON with:
{{
  "entity_name": "singular noun like Patient, Product, Transaction, etc.",
  "entity_type": "one of: business, geographic, measurement, temporal, categorical",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Be specific and use domain-appropriate terms. For example:
- If it's medical data about patients, return "Patient"
- If it's product catalog data, return "Product"
- If it's diamond specifications, return "Diamond"
"""
        
        try:
            response = self.llm_manager.complete(prompt, temperature=0, response_format={"type": "json_object"})
            result = json.loads(response) if isinstance(response, str) else response
            
            entity_name = result.get("entity_name", "Entity")
            confidence = float(result.get("confidence", 0.5))
            
            # Cache the result
            self._save_llm_cache(cache_key, {"name": entity_name, "confidence": confidence})
            
            logger.info(f"LLM inferred entity name: '{entity_name}' with confidence {confidence}")
            return entity_name, confidence
            
        except Exception as e:
            logger.warning(f"LLM entity name inference failed: {e}")
            return "Entity", 0.3
    
    def _llm_binary_semantic_check(self, question: str, context: str, cache_suffix: str) -> tuple[bool, float]:
        """Ask a binary semantic question to the LLM."""
        if not self.llm_manager:
            return False, 0.0
        
        # Check cache first
        cache_key = self._llm_cache_key(f"binary_{cache_suffix}", context)
        
        if cached := self._get_llm_cached(cache_key):
            return cached["answer"], cached["confidence"]
        
        prompt = f"""Answer this binary question about the dataset:

{question}

Context:
{context}

Return a JSON with:
{{
  "answer": true or false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Be precise and only answer true if you are confident."""
        
        try:
            response = self.llm_manager.complete(prompt, temperature=0, response_format={"type": "json_object"})
            result = json.loads(response) if isinstance(response, str) else response
            
            answer = bool(result.get("answer", False))
            confidence = float(result.get("confidence", 0.5))
            
            # Cache the result
            self._save_llm_cache(cache_key, {"answer": answer, "confidence": confidence})
            
            return answer, confidence
            
        except Exception as e:
            logger.warning(f"LLM binary check failed: {e}")
            return False, 0.0
    
    def _llm_infer_entity_name_from_column(self, column_name: str, columns: list[ColumnProfile]) -> tuple[str, float]:
        """Use LLM to infer entity name from column name and context."""
        if not self.llm_manager:
            return column_name.capitalize(), 0.5
        
        # Check cache first
        cache_content = f"{column_name}_{[c.name for c in columns[:5]]}"
        cache_key = self._llm_cache_key("entity_name_column", cache_content)
        
        if cached := self._get_llm_cached(cache_key):
            return cached["name"], cached["confidence"]
        
        # Prepare context
        column_info = []
        for col in columns[:5]:  # Use first 5 columns for context
            col_info = f"- {col.name} ({col.data_type.value})"
            if col.sample_values and len(col.sample_values) > 0:
                samples = str(col.sample_values[:3])
                col_info += f" samples: {samples}"
            column_info.append(col_info)
        
        prompt = f"""Analyze this dataset column and determine what entity type it represents.

First column (entity identifier): {column_name}
Dataset structure:
{chr(10).join(column_info)}

This appears to be a time-series dataset where each row represents one instance of the same entity type,
and the first column identifies what that entity is.

What type of entity does the column '{column_name}' represent? Examples:
- 'country' → 'Country'
- 'region' → 'Region' 
- 'product' → 'Product'
- 'customer' → 'Customer'
- 'patient' → 'Patient'
- 'company' → 'Company'

Return a JSON with:
{{
  "entity_name": "singular noun like Country, Product, Customer, etc.",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Be specific and use proper capitalization.
"""
        
        try:
            response = self.llm_manager.complete(prompt, temperature=0, response_format={"type": "json_object"})
            result = json.loads(response) if isinstance(response, str) else response
            
            entity_name = result.get("entity_name", column_name.capitalize())
            confidence = float(result.get("confidence", 0.7))
            
            # Cache the result
            self._save_llm_cache(cache_key, {"name": entity_name, "confidence": confidence})
            
            logger.info(f"LLM inferred entity from column '{column_name}': '{entity_name}' with confidence {confidence}")
            return entity_name, confidence
            
        except Exception as e:
            logger.warning(f"LLM column entity name inference failed: {e}")
            return column_name.capitalize(), 0.5
    
    def _llm_detect_domain(self, columns: list[ColumnProfile], sample_rows: list[dict] = None) -> str:
        """Use LLM to detect the business domain of the dataset."""
        if not self.llm_manager:
            return "generic"
        
        # Check cache
        cache_content = f"{[c.name for c in columns[:20]]}"
        cache_key = self._llm_cache_key("domain", cache_content)
        
        if cached := self._get_llm_cached(cache_key):
            return cached["domain"]
        
        column_names = [c.name for c in columns[:20]]
        
        prompt = f"""Analyze these dataset columns and identify the business domain.

Columns: {column_names}

Common domains include:
- healthcare (medical, patients, treatments, diagnosis)
- finance (transactions, accounts, payments, investments)
- retail (products, customers, orders, inventory)
- manufacturing (production, materials, quality, supply chain)
- education (students, courses, grades, enrollment)
- government (citizens, services, regulations, compliance)
- technology (software, hardware, users, systems)
- agriculture (crops, farming, land, production)
- transportation (vehicles, routes, logistics, shipping)
- real_estate (properties, listings, sales, rentals)
- hospitality (hotels, bookings, guests, services)
- energy (consumption, production, utilities, resources)
- telecommunications (calls, data, networks, subscribers)
- insurance (policies, claims, premiums, coverage)
- media (content, viewers, engagement, advertising)

Return a JSON with:
{{
  "domain": "domain name from above list or 'generic' if unclear",
  "confidence": 0.0-1.0,
  "indicators": ["list", "of", "key", "indicators"]
}}"""
        
        try:
            response = self.llm_manager.complete(prompt, temperature=0, response_format={"type": "json_object"})
            result = json.loads(response) if isinstance(response, str) else response
            
            domain = result.get("domain", "generic")
            
            # Cache the result
            self._save_llm_cache(cache_key, {"domain": domain})
            
            logger.info(f"LLM detected domain: '{domain}'")
            return domain
            
        except Exception as e:
            logger.warning(f"LLM domain detection failed: {e}")
            return "generic"
    
    def _llm_classify_entity_type(self, entity_name: str, column_names: list[str]) -> str:
        """Use LLM to classify the entity type."""
        if not self.llm_manager:
            return EntityType.TABLE.value
        
        # Check cache
        cache_content = f"{entity_name}_{column_names[:10]}"
        cache_key = self._llm_cache_key("entity_type", cache_content)
        
        if cached := self._get_llm_cached(cache_key):
            return cached["entity_type"]
        
        prompt = f"""Classify the entity type for: {entity_name}

Associated columns: {column_names[:10]}

Entity types:
- table: Generic tabular data
- business: Business entities (customers, products, transactions, etc.)
- geographic: Geographic locations (countries, cities, regions, etc.)
- temporal: Time-based entities
- identifier: IDs and keys
- measurement: Metrics and measurements
- categorical: Categories and classifications

Return JSON:
{{
  "entity_type": "one of the above types",
  "confidence": 0.0-1.0
}}"""
        
        try:
            response = self.llm_manager.complete(prompt, temperature=0, response_format={"type": "json_object"})
            result = json.loads(response) if isinstance(response, str) else response
            
            entity_type = result.get("entity_type", "table")
            
            # Map to our EntityType enum values
            type_mapping = {
                "business": EntityType.BUSINESS.value,
                "geographic": EntityType.GEOGRAPHIC.value,
                "temporal": EntityType.TEMPORAL.value,
                "identifier": EntityType.IDENTIFIER.value,
                "measurement": EntityType.MEASUREMENT.value,
                "categorical": EntityType.CATEGORICAL.value,
                "table": EntityType.TABLE.value
            }
            
            entity_type = type_mapping.get(entity_type, EntityType.TABLE.value)
            
            # Cache the result
            self._save_llm_cache(cache_key, {"entity_type": entity_type})
            
            return entity_type
            
        except Exception as e:
            logger.warning(f"LLM entity type classification failed: {e}")
            return EntityType.TABLE.value

    # ---------- public API ----------
    def extract_entities(
        self,
        file_path: str,
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Entity]:
        """Top-level entry: deterministic run with caching."""
        logger.info(f"Extracting entities from {file_path}")

        # Use LangGraph extractor if available
        if self.use_langgraph and self._langgraph_extractor:
            try:
                return self._langgraph_extractor.extract_entities(file_path, columns, config)
            except Exception as e:
                logger.warning(f"LangGraph extraction failed, falling back to traditional: {e}")
                self.use_langgraph = False  # Disable for future calls
        
        # Traditional extraction
        file_hash = _hash_file(file_path)
        cached = self._load_cached_entities(file_hash)
        if cached is not None:
            logger.info("Returning cached entities")
            return cached

        entities = self._extract_entities_traditional(file_path, columns, config)

        try:
            self._save_cached_entities(file_hash, entities)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
        return entities

    # ---------- caching ----------
    def _cache_path(self, key: str, suffix: str = ".json") -> Path | None:
        if not self.cache_dir:
            return None
        p = self.cache_dir / f"{key}{suffix}"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load_cached_entities(self, file_hash: str) -> list[Entity] | None:
        path = self._cache_path(file_hash)
        if path and path.exists():
            try:
                data = json.loads(path.read_text())
                return [Entity(**e) for e in data]
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")
        return None

    def _save_cached_entities(self, file_hash: str, entities: list[Entity]) -> None:
        path = self._cache_path(file_hash)
        if not path:
            return
        payload = [e.model_dump() for e in entities]
        path.write_text(json.dumps(payload, ensure_ascii=False))

    # ---------- main extraction logic ----------
    def _extract_entities_traditional(
        self,
        file_path: str,
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Entity]:
        """Main extraction logic with intelligent entity detection.
        
        Decision flow:
        1. Check if it's a time-series multi-entity dataset (e.g., countries with measurements over years)
           -> Extract entities for identifiers and measurements separately
        2. Check if it's a regular tabular dataset (e.g., list of patients, products, etc.)
           -> Extract a single table-level entity with all columns as attributes  
        3. Fallback to column-level extraction for unclear cases
        
        Configuration options:
        - use_llm: Enable/disable LLM usage (default: True)
        - llm_strategy: 'none', 'hybrid', 'aggressive' (default: 'hybrid')
        - llm_for_entity_naming: Use LLM for entity name inference (default: True)
        - llm_for_domain_detection: Use LLM for domain detection (default: True)
        - llm_for_entity_typing: Use LLM for entity type classification (default: True)
        """
        self.current_file_path = file_path
        
        # Configure LLM usage based on config
        use_llm = _safe_config_get(config, "use_llm", True)
        llm_strategy = _safe_config_get(config, "llm_strategy", "hybrid")
        
        # Temporarily disable LLM if requested
        original_llm_manager = self.llm_manager
        if not use_llm or llm_strategy == "none":
            self.llm_manager = None
            logger.info("LLM usage disabled for this extraction")
        
        # Read the data for analysis
        df = self._safe_read_csv(file_path, usecols=[c.name for c in columns])
        
        # Check if this is a special case: multi-entity dataset
        if self._is_multi_entity_dataset(columns):
            if self._is_time_series_dataset(columns):
                logger.info("Detected time-series multi-entity dataset, using semantic extraction")
            else:
                logger.info("Detected relational multi-entity dataset, using semantic extraction")
            semantic_entities = self._extract_semantic_entities(df, columns, config)
            if semantic_entities:
                return semantic_entities
        
        # For regular tabular data, try table-level entity extraction
        # This is ideal for datasets where each row represents one instance of the same entity
        table_entities = self._extract_table_level_entities(columns, config)
        if table_entities:
            logger.info(f"Using table-level entity: {table_entities[0].name}")
            return table_entities
        
        # If table-level extraction didn't work, try semantic extraction
        logger.info("Attempting semantic entity extraction...")
        semantic_entities = self._extract_semantic_entities(df, columns, config)
        
        # Last resort: Extract entities per column if semantic extraction fails
        if not semantic_entities:
            logger.info("Semantic extraction failed, falling back to column-level extraction")
            semantic_entities = self._extract_column_level_entities(df, columns, config)

        # Optional business-level entities; gated & cached inside
        per_dataset: list[Entity] = []
        if _safe_config_get(config, "use_llm", True) and _safe_config_get(
            config, "extract_business_entities", False
        ):
            try:
                per_dataset = self._extract_business_entities_llm(df, columns, config)
            except Exception as e:
                logger.warning(f"Business LLM extraction skipped: {e}")

        # Combine all entities
        all_entities = semantic_entities + per_dataset
        
        # Deduplicate by meaning
        if _safe_config_get(config, "use_intelligent_consolidation", True):
            all_entities = self._deduplicate_by_embeddings(all_entities, config)

        # Drop low-confidence
        thr = float(_safe_config_get(config, "confidence_threshold", 0.70))
        entities = [e for e in all_entities if float(getattr(e, "confidence", 1.0)) >= thr]

        # Optionally cap count
        max_entities = int(_safe_config_get(config, "max_entities", 100_000))
        if len(entities) > max_entities:
            entities = entities[:max_entities]
        
        # Restore original LLM manager if it was temporarily disabled
        if not use_llm or llm_strategy == "none":
            self.llm_manager = original_llm_manager
        
        logger.info(f"Total entities extracted: {len(entities)}")
        return entities

    def _extract_table_level_entities(
        self, 
        columns: list[ColumnProfile], 
        config: dict[str, Any]
    ) -> list[Entity]:
        """Extract a table-level entity with all columns as attributes.
        
        This is used for regular tabular datasets where each row represents
        one instance of the same entity (e.g., diamonds, patients, products).
        """
        try:
            # Infer what each row represents from the filename
            entity_name = self._infer_meaningful_entity_name(self.current_file_path, columns, config)
            
            # Don't create a generic "Entity" or "Record" unless absolutely necessary
            if entity_name in ['Entity', 'Record']:
                logger.info(f"Could not infer meaningful entity name, skipping table-level extraction")
                return []
                
            logger.info(f"Inferred entity name: '{entity_name}' from file path: '{self.current_file_path}'")
            
            # Create attributes from all columns
            attributes = []
            for column in columns:
                attribute = Attribute(
                    name=column.name,
                    data_type=column.data_type,
                    source_column=column.name,
                    confidence=0.95,  # High confidence for direct column mapping
                    statistics=column.statistics,
                    sample_values=column.sample_values
                )
                attributes.append(attribute)
            
            # Determine the appropriate entity type based on the entity name and columns
            entity_type = self._determine_entity_type(entity_name, columns)
            
            # Create the main entity
            entity = Entity(
                id=str(uuid.uuid4()),
                name=entity_name,
                entity_type=entity_type,
                attributes=attributes,
                confidence=1.0,  # High confidence for table-level entity
                source_table=self.current_file_path
            )
            logger.info(f"Created entity: id='{entity.id}', name='{entity.name}', type='{entity.entity_type}'")
            
            return [entity]
            
        except Exception as e:
            logger.warning(f"Table-level entity extraction failed: {e}")
            return []

    def _determine_entity_type(self, entity_name: str, columns: list[ColumnProfile] = None) -> str:
        """Determine the appropriate entity type using LLM-driven approach."""
        
        # Always try LLM first if available (truly scalable)
        if self.llm_manager and columns:
            column_names = [col.name for col in columns[:10]]
            entity_type = self._llm_classify_entity_type(entity_name, column_names)
            logger.info(f"LLM classification: {entity_name} -> {entity_type}")
            return entity_type
        
        # Fallback: Simple heuristics only when LLM unavailable
        entity_name_lower = entity_name.lower()
        
        # Only use basic patterns as absolute fallback
        if any(word in entity_name_lower for word in ['country', 'region', 'state', 'city', 'location']):
            logger.info(f"Fallback classification: {entity_name} -> GEOGRAPHIC")
            return EntityType.GEOGRAPHIC.value
        elif any(word in entity_name_lower for word in ['measurement', 'metric', 'score', 'rate', 'percentage']):
            logger.info(f"Fallback classification: {entity_name} -> MEASUREMENT")
            return EntityType.MEASUREMENT.value
        elif any(word in entity_name_lower for word in ['date', 'time', 'period', 'duration']):
            logger.info(f"Fallback classification: {entity_name} -> TEMPORAL")
            return EntityType.TEMPORAL.value
        else:
            # Default to business for most entities when LLM unavailable
            logger.info(f"Default classification: {entity_name} -> BUSINESS")
            return EntityType.BUSINESS.value
    
    def _is_time_series_dataset(self, columns: list[ColumnProfile]) -> bool:
        """Check if the dataset represents time-series data."""
        # Count how many columns look like years
        year_columns = 0
        for col in columns:
            col_name = str(col.name)
            # Check if column name is a year (4 digits between 1900-2100)
            if col_name.isdigit() and len(col_name) == 4:
                year = int(col_name)
                if 1900 <= year <= 2100:
                    year_columns += 1
            # Also check for month/quarter patterns
            elif any(pattern in col_name.lower() for pattern in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                                                                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
                                                                  'q1', 'q2', 'q3', 'q4', 'quarter']):
                year_columns += 1
        
        # If more than 30% of columns are time-related, it's likely time-series
        return year_columns > len(columns) * 0.3
    
    def _is_multi_entity_dataset(self, columns: list[ColumnProfile]) -> bool:
        """Check if the dataset contains multiple entity types."""
        if not columns:
            return False
        
        # Common entity identifier patterns
        entity_keywords = ['country', 'region', 'state', 'city', 'product', 'customer', 
                          'supplier', 'employee', 'department', 'category', 'group',
                          'company', 'organization', 'location', 'branch', 'store',
                          'patient', 'user', 'account', 'order', 'transaction', 'address']
        
        # Count how many entity types we can identify
        entity_types_found = set()
        
        for col in columns:
            col_name_lower = col.name.lower()
            
            # Check for direct entity keywords
            for keyword in entity_keywords:
                if keyword in col_name_lower:
                    entity_types_found.add(keyword)
            
            # Check for ID patterns (entity_id, entityId, etc.)
            if '_id' in col_name_lower and col.data_type in [DataType.STRING, DataType.INTEGER]:
                # Extract entity type from column name like "customer_id" -> "customer"
                entity_type = col_name_lower.replace('_id', '')
                if entity_type in entity_keywords:
                    entity_types_found.add(entity_type)
        
        # If we found multiple entity types or at least one clear entity reference, it's multi-entity
        return len(entity_types_found) >= 1
    
    def _is_single_entity_with_time_series(self, columns: list[ColumnProfile]) -> bool:
        """Check if this is a single entity type with time-series measurements (e.g., countries with data over years)."""
        if not columns:
            return False
        
        # Check if first column is a single entity identifier (not multiple entity types)
        first_col = columns[0]
        first_col_name_lower = first_col.name.lower()
        
        # Single entity identifiers (each row represents one instance of the same entity type)
        single_entity_keywords = ['country', 'region', 'state', 'city', 'product', 'customer', 
                                 'patient', 'employee', 'company', 'organization', 'location']
        
        # Check if first column suggests single entity type
        if any(keyword in first_col_name_lower for keyword in single_entity_keywords):
            # Also check if it's a string column (typical for entity identifiers)
            if first_col.data_type == DataType.STRING:
                # Count time columns
                time_cols = [col for col in columns[1:] if self._is_time_column(col.name)]
                # If we have many time columns, this is likely single entity with time-series
                return len(time_cols) > len(columns) * 0.5  # More than 50% are time columns
        
        return False
    
    def _extract_time_series_entities(self, df: pd.DataFrame, columns: list[ColumnProfile], config: dict[str, Any], dataset_context: dict[str, Any]) -> list[Entity]:
        """Extract entities from time-series multi-entity datasets."""
        entities: list[Entity] = []
        
        # First column is usually the entity identifier (e.g., country, product, etc.)
        first_col = columns[0]
        
        # Create entity from the identifier column
        if first_col.data_type == DataType.STRING:
            # Use the new LLM-based entity naming approach
            entity_name = self._infer_meaningful_entity_name(self.current_file_path, columns, config)
            entity_type = self._determine_entity_type(entity_name, columns)
            
            # Create entity with the identifier as attribute
            attribute = Attribute(
                name=first_col.name,
                data_type=first_col.data_type,
                source_column=first_col.name,
                confidence=0.95,
                statistics=first_col.statistics,
                sample_values=first_col.sample_values
            )
            
            entity = Entity(
                name=entity_name,
                entity_type=entity_type,
                attributes=[attribute],
                confidence=0.95,
                source_table=self.current_file_path
            )
            entity.id = self._generate_entity_id(entity)
            entities.append(entity)
            logger.info(f"Created {entity_type} entity '{entity_name}' from identifier column '{first_col.name}'")
            
            # Now handle the time-series measurements
            time_cols = []
            for col in columns[1:]:  # Skip the first column (entity identifier)
                if self._is_time_column(col.name):
                    time_cols.append(col)
            
            if time_cols:
                # Create a measurement entity for the time-series data
                measurement_name = self._infer_measurement_name_from_filename(self.current_file_path, columns)
                
                # Create attributes for all time columns
                attributes = []
                for col in time_cols:
                    attribute = Attribute(
                        name=col.name,
                        data_type=col.data_type,
                        source_column=col.name,
                        confidence=0.90,
                        statistics=col.statistics,
                        sample_values=col.sample_values
                    )
                    attributes.append(attribute)
                
                entity = Entity(
                    name=measurement_name,
                    entity_type=EntityType.MEASUREMENT.value,
                    attributes=attributes,
                    confidence=0.90,
                    source_table=self.current_file_path
                )
                entity.id = self._generate_entity_id(entity)
                entities.append(entity)
                logger.info(f"Created measurement entity '{measurement_name}' from {len(time_cols)} time-series columns")
            
            return entities
        
        return []
    
    def _extract_relational_entities(self, df: pd.DataFrame, columns: list[ColumnProfile], config: dict[str, Any], dataset_context: dict[str, Any]) -> list[Entity]:
        """Extract entities from relational multi-entity datasets using LLM-driven decisions."""
        entities: list[Entity] = []
        
        # Prepare context for LLM
        column_info = []
        for col in columns[:10]:  # Limit for context
            col_info = f"- {col.name} ({col.data_type.value})"
            if col.sample_values and len(col.sample_values) > 0:
                samples = str(col.sample_values[:3])
                col_info += f" samples: {samples}"
            column_info.append(col_info)
        
        context = f"""Dataset columns:
{chr(10).join(column_info)}"""
        
        # Step 1: Identify primary entities using LLM or fallback heuristics
        primary_entity_columns = []
        for col in columns:
            is_primary, confidence = self._llm_binary_semantic_check(
                f"Is the column '{col.name}' a primary entity identifier (represents a main business object like customer, product, order, etc.)?",
                context, f"primary_entity_{col.name}"
            )
            
            # Generic fallback when LLM is not available
            if not self.llm_manager:
                col_name_lower = col.name.lower()
                
                # Generic pattern: any column ending with '_id' is likely a primary entity
                if '_id' in col_name_lower and col.data_type in [DataType.STRING, DataType.INTEGER]:
                    is_primary, confidence = True, 0.7
            
            if is_primary and confidence >= 0.7:
                primary_entity_columns.append(col)
                logger.info(f"Column '{col.name}' identified as primary entity (confidence: {confidence})")
        
        # Step 2: Group related columns using LLM
        entity_groups = {}  # entity_name -> [columns]
        used_columns = set()
        
        logger.info(f"Found {len(primary_entity_columns)} primary entity columns: {[col.name for col in primary_entity_columns]}")
        
        for primary_col in primary_entity_columns:
            # Infer entity name from primary column
            entity_name = self._infer_entity_name_from_primary_column(primary_col)
            logger.info(f"Processing primary column '{primary_col.name}' → entity '{entity_name}'")
            
            # Find related columns for this entity
            related_columns = [primary_col]
            used_columns.add(primary_col.name)
            
            for col in columns:
                if col.name in used_columns:
                    continue
                
                # Ask LLM if this column is related to the primary entity
                is_related, confidence = self._llm_binary_semantic_check(
                    f"Is the column '{col.name}' an attribute or property of the entity '{entity_name}' (represented by column '{primary_col.name}')?",
                    context, f"related_{entity_name}_{col.name}"
                )
                
                # Generic fallback when LLM is not available - be very conservative
                if not self.llm_manager:
                    # NEVER group columns that end with '_id' - they are likely separate entities
                    col_name_lower = col.name.lower()
                    if '_id' in col_name_lower:
                        is_related, confidence = False, 0.0
                    else:
                        # Only group non-ID columns with low confidence
                        is_related, confidence = True, 0.4
                
                if is_related and confidence > 0.5:
                    related_columns.append(col)
                    used_columns.add(col.name)
                    logger.info(f"Column '{col.name}' grouped with entity '{entity_name}' (confidence: {confidence})")
            
            entity_groups[entity_name] = related_columns
        
        # Step 3: Handle remaining columns - check if they form their own entities
        remaining_columns = [col for col in columns if col.name not in used_columns]
        
        if remaining_columns:
            # Ask LLM if remaining columns form a cohesive entity
            remaining_col_names = [col.name for col in remaining_columns]
            forms_entity, confidence = self._llm_binary_semantic_check(
                f"Do these remaining columns form a cohesive entity: {remaining_col_names}?",
                context, f"remaining_entity_{len(remaining_columns)}"
            )
            
            # Generic fallback when LLM is not available
            if not self.llm_manager:
                # Simple heuristic: if we have multiple unused columns, they likely form an entity
                if len(remaining_columns) >= 4:
                    forms_entity, confidence = True, 0.7
                elif len(remaining_columns) >= 2:
                    forms_entity, confidence = True, 0.6
            
            if forms_entity and confidence > 0.5:
                # Infer entity name for the group
                entity_name = self._infer_entity_name_from_column_group(remaining_columns)
                entity_groups[entity_name] = remaining_columns
                logger.info(f"Remaining columns grouped as entity '{entity_name}' (confidence: {confidence})")
        
        # Step 4: Create entities from groups
        logger.info(f"Entity groups to create: {list(entity_groups.keys())}")
        for entity_name, cols in entity_groups.items():
            # Determine entity type using LLM
            entity_type = self._determine_entity_type(entity_name, cols)
            
            # Create attributes
            attributes = []
            for col in cols:
                attribute = Attribute(
                    name=col.name,
                    data_type=col.data_type,
                    source_column=col.name,
                    confidence=0.85,
                    statistics=col.statistics,
                    sample_values=col.sample_values
                )
                attributes.append(attribute)
            
            entity = Entity(
                name=entity_name,
                entity_type=entity_type,
                attributes=attributes,
                confidence=0.85,
                source_table=self.current_file_path
            )
            entity.id = self._generate_entity_id(entity)
            entities.append(entity)
            logger.info(f"Created {entity_type} entity '{entity_name}' from {len(attributes)} columns")
        
        return entities
    
    def _infer_entity_name_from_primary_column(self, col: ColumnProfile) -> str:
        """Infer entity name from a primary column."""
        col_name = col.name.lower()
        
        # Remove common suffixes
        if col_name.endswith('_id'):
            entity_name = col_name[:-3]
        elif col_name.endswith('id'):
            entity_name = col_name[:-2]
        else:
            entity_name = col_name
        
        return entity_name.capitalize()
    
    def _infer_entity_name_from_column_group(self, columns: list[ColumnProfile]) -> str:
        """Infer entity name from a group of columns using LLM."""
        if not self.llm_manager:
            # Generic fallback: use the first column name as basis for entity name
            if columns:
                first_col = columns[0].name.lower()
                # Remove common suffixes and capitalize
                if '_id' in first_col:
                    return first_col.replace('_id', '').capitalize()
                elif '_type' in first_col:
                    return first_col.replace('_type', '').capitalize()
                else:
                    return first_col.capitalize()
            return "Entity"
        
        # Prepare column context
        column_names = [col.name for col in columns[:5]]
        
        # Check cache
        cache_content = f"group_{column_names}"
        cache_key = self._llm_cache_key("group_entity_name", cache_content)
        
        if cached := self._get_llm_cached(cache_key):
            return cached["name"]
        
        prompt = f"""What single entity do these columns represent?

Columns: {column_names}

Return a JSON with:
{{
  "entity_name": "singular noun like Address, Location, Contact, etc.",
  "confidence": 0.0-1.0
}}"""
        
        try:
            response = self.llm_manager.complete(prompt, temperature=0, response_format={"type": "json_object"})
            result = json.loads(response) if isinstance(response, str) else response
            
            entity_name = result.get("entity_name", "Entity")
            
            # Cache the result
            self._save_llm_cache(cache_key, {"name": entity_name})
            
            return entity_name
            
        except Exception as e:
            logger.warning(f"LLM group entity name inference failed: {e}")
            return "Entity"
    
    def _infer_meaningful_entity_name(self, file_path: str, columns: list[ColumnProfile], config: dict[str, Any] = None) -> str:
        """Infer a semantically meaningful entity name using hybrid approach: rules + LLM fallback."""
        from pathlib import Path
        import re
        
        # Special case: For time-series datasets, infer entity name from first column, not filename
        if self._is_time_series_dataset(columns) and self._is_single_entity_with_time_series(columns):
            first_col = columns[0]
            if first_col.data_type == DataType.STRING:
                # Use LLM to infer entity name from column name and context
                if self.llm_manager:
                    entity_name, confidence = self._llm_infer_entity_name_from_column(first_col.name, columns)
                    if confidence >= 0.6:  # Lower threshold for column-based inference
                        logger.info(f"LLM inferred entity from column '{first_col.name}': {entity_name}")
                        return entity_name
                
                # Fallback: Use column name directly
                entity_name = first_col.name.capitalize()
                logger.info(f"Using column name as entity: {entity_name}")
                return entity_name
        
        # Get base filename without extension
        filename = Path(file_path).stem.lower()
        original_filename = filename
        
        # Clean up common prefixes/suffixes
        cleanup_patterns = ['sample_', 'test_', 'demo_', 'temp_', 'tmp_', 'export_', 'import_', 
                           '_data', '_dataset', '_table', '_csv', '_export', '_import', '_file']
        for pattern in cleanup_patterns:
            filename = filename.replace(pattern, '')
        
        # Remove numbers at the beginning or end (like top_100, 2024_, etc)
        filename = re.sub(r'^\d+_|_\d+$', '', filename)
        filename = re.sub(r'^top_\d+_', '', filename)  # Remove "top_N_" patterns
        
        # Split by underscores and hyphens
        parts = re.split(r'[_\-]', filename)
        
        # Filter out noise words and descriptors
        noise_words = ['of', 'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 
                       'from', 'about', 'all', 'new', 'old', 'top', 'high', 'low', 'risk',
                       'list', 'data', 'info', 'information', 'details', 'records']
        
        # Keep only meaningful parts
        meaningful_parts = [p for p in parts if p and p not in noise_words]
        
        # Step 1: Try LLM first if available (truly scalable)
        use_llm_naming = True
        if config:
            use_llm_naming = _safe_config_get(config, "llm_for_entity_naming", True)
        
        if self.llm_manager and use_llm_naming:
            entity_name, confidence = self._llm_infer_entity_name(original_filename, columns)
            if confidence >= self.confidence_thresholds.get("llm_structured", 0.7):
                logger.info(f"LLM extraction found entity: {entity_name} (confidence: {confidence})")
                return entity_name
        
        # Step 2: Try heuristics as fallback (only when LLM unavailable or low confidence)
        if meaningful_parts:
            # Check for plural forms and singularize
            last_part = meaningful_parts[-1]
            if last_part.endswith('ies'):
                # companies -> company, policies -> policy
                singular = last_part[:-3] + 'y'
                entity_name = singular.capitalize()
                if entity_name not in ['Entity', 'Record']:  # Avoid generic names
                    logger.info(f"Heuristic extraction found entity: {entity_name}")
                    return entity_name
            elif last_part.endswith('es'):
                # houses -> house, buses -> bus  
                entity_name = last_part[:-2].capitalize()
                if entity_name not in ['Entity', 'Record']:
                    logger.info(f"Heuristic extraction found entity: {entity_name}")
                    return entity_name
            elif last_part.endswith('s') and len(last_part) > 3:
                # patients -> patient, diamonds -> diamond
                entity_name = last_part[:-1].capitalize()
                if entity_name not in ['Entity', 'Record']:
                    logger.info(f"Heuristic extraction found entity: {entity_name}")
                    return entity_name
            elif len(last_part) > 2:  # Meaningful word
                entity_name = last_part.capitalize()
                if entity_name not in ['Entity', 'Record']:
                    logger.info(f"Heuristic extraction found entity: {entity_name}")
                    return entity_name
        
        # Step 3: Last resort - try LLM with lower confidence threshold
        if self.llm_manager and use_llm_naming:
            entity_name, confidence = self._llm_infer_entity_name(original_filename, columns)
            if confidence >= self.confidence_thresholds.get("llm_general", 0.5):
                logger.info(f"LLM fallback found entity: {entity_name} (confidence: {confidence})")
                return entity_name
        
        # Step 4: Absolute fallback
        if columns and columns[0].name.lower() in ['id', 'uid', 'uuid', 'identifier']:
            return 'Record'
        
        return 'Entity'

    def _extract_column_level_entities(
        self,
        df: pd.DataFrame,
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Entity]:
        """Extract entities at the column level as fallback."""
        entities: list[Entity] = []
        
        for col in columns[: int(_safe_config_get(config, "max_columns_to_process", 10_000))]:
            try:
                logger.info(f"Extracting entities for column: {col.name}")
                col_entities = self._extract_column_entities(df, col, config)
                entities.extend(col_entities)
                logger.info(f"Column {col.name}: extracted {len(col_entities)} entities")
            except Exception as e:
                logger.warning(f"Entity extraction failed for column {col.name}: {e}")

        return entities

    # ---------- Column-level entity extraction (fallback) ----------
    def _extract_column_entities(
        self,
        df: pd.DataFrame,
        column: ColumnProfile,
        config: dict[str, Any],
    ) -> list[Entity]:
        """Collect candidates per column, then pick one best entity unless disabled."""
        entities: list[Entity] = []
        name = column.name
        s = df[name]

        # Strategy 1: regex/validator-based types (deterministic)
        regex_entities = self._extract_regex_entities(s, column, config)
        entities.extend(regex_entities)

        # Hard exit if we got a highly-specific, high-confidence type
        hard_exit_types = {
            EntityType.EMAIL.value,
            EntityType.URL.value,
            EntityType.IP_ADDRESS.value,
            EntityType.UUID.value,
            EntityType.PHONE.value,
            EntityType.DATE.value,
            EntityType.TIME.value,
            EntityType.POSTAL_CODE.value,
        }
        top_regex = max(regex_entities, key=lambda e: e.confidence, default=None)
        if (
            top_regex
            and top_regex.entity_type in hard_exit_types
            and top_regex.confidence >= 0.90
        ):
            return [top_regex]

        # Strategy 2: ID/sequential/uniqueness analysis
        if column.data_type in [DataType.INTEGER, DataType.STRING]:
            entities.extend(self._extract_id_entities(s, column, config))

        # Strategy 3: pattern-based (percent/latlon/year/etc.)
        entities.extend(self._extract_pattern_entities(s, column, config))

        # Strategy 4: basic categorical detection (generic)
        entities.extend(self._extract_categorical_entities(s, column, config))

        # Strategy 5 (LLM): only if nothing else found with confidence
        if _safe_config_get(config, "use_llm", True) and not entities:
            try:
                entities.extend(self._extract_llm_entities(s, column, config))
            except Exception as e:
                logger.warning(f"LLM extraction failed for column {name}: {e}")

        # Final choice: pick exactly one entity per column (default)
        if _safe_config_get(config, "one_entity_per_column", True) and entities:
            return [self._choose_best_entity(entities, column, config)]
        return entities

    # ---------- Gate A: validators & regex ----------
    def _extract_regex_entities(
        self, s: pd.Series, column: ColumnProfile, config: dict[str, Any]
    ) -> list[Entity]:
        values = self._det_sample_unique_sorted(s, config)
        n = max(len(values), 1)

        def ratio(rx: re.Pattern) -> float:
            cnt = 0
            for v in values:
                v = str(v).strip()
                if not v:
                    continue
                if rx.match(v):
                    cnt += 1
            return cnt / n

        out: list[Entity] = []
        checks: list[tuple[str, re.Pattern]] = [
            (EntityType.EMAIL.value, _REG_EMAIL),
            (EntityType.IP_ADDRESS.value, _REG_IP),
            (EntityType.UUID.value, _REG_UUID),
            (EntityType.PHONE.value, _REG_PHONE),
            (EntityType.POSTAL_CODE.value, _REG_POSTAL_5),
            (EntityType.URL.value, _REG_URL),  # URL check moved to end to avoid false positives with years
        ]
        for t, rx in checks:
            r = ratio(rx)
            if r >= 0.70:  # strong validator
                # Create attribute for this column
                attribute = Attribute(
                    name=column.name,
                    data_type=column.data_type,
                    source_column=column.name,
                    confidence=float(r),
                    statistics=column.statistics,
                    sample_values=column.sample_values
                )
                
                entity = Entity(
                    name=column.name,
                    entity_type=t,
                    attributes=[attribute],
                    confidence=float(r),
                    source_table=self.current_file_path
                )
                entity.id = self._generate_entity_id(entity)
                out.append(entity)
        return out

    # ---------- Gate A: ID/sequential/uniqueness ----------
    def _extract_id_entities(
        self, s: pd.Series, column: ColumnProfile, config: dict[str, Any]
    ) -> list[Entity]:
        out: list[Entity] = []
        non_null = s.dropna()
        if non_null.empty:
            return out

        # uniqueness ratio
        uniq = non_null.astype(str).nunique()
        ur = uniq / len(non_null)

        # monotonic increase ⇒ candidate sequential id
        try:
            as_int = pd.to_numeric(non_null, errors="coerce")
            monotonic = bool(as_int.is_monotonic_increasing)
        except Exception:
            monotonic = False

        # uuid-like detection (looser than strict UUID)
        sample = self._det_sample_unique_sorted(non_null, config)
        loose_uuid_hits = sum(
            1 for v in sample if _REG_HEXISH_UUID.match(str(v).strip())
        )
        loose_ratio = loose_uuid_hits / max(len(sample), 1)

        # Decision rules
        name_lower = column.name.lower()
        id_prior = ("id" in name_lower) or (name_lower.endswith("_id"))

        # Create attribute for this column
        attribute = Attribute(
            name=column.name,
            data_type=column.data_type,
            source_column=column.name,
            confidence=float(min(1.0, 0.7 + 0.3 * ur)),
            statistics=column.statistics,
            sample_values=column.sample_values
        )

        if ur >= 0.98 and (monotonic or id_prior):
            entity = Entity(
                name=column.name,
                entity_type=EntityType.SEQUENTIAL_ID.value if monotonic else EntityType.IDENTIFIER.value,
                attributes=[attribute],
                confidence=float(min(1.0, 0.7 + 0.3 * ur)),
                source_table=self.current_file_path
            )
            entity.id = self._generate_entity_id(entity)
            out.append(entity)
        elif ur >= 0.95 or loose_ratio >= 0.7:
            entity = Entity(
                name=column.name,
                entity_type=EntityType.IDENTIFIER.value,
                attributes=[attribute],
                confidence=float(max(0.70, min(0.95, ur))),
                source_table=self.current_file_path
            )
            entity.id = self._generate_entity_id(entity)
            out.append(entity)
        return out

    # ---------- Gate A: other patterns (percent/latlon/year) ----------
    def _extract_pattern_entities(
        self, s: pd.Series, column: ColumnProfile, config: dict[str, Any]
    ) -> list[Entity]:
        out: list[Entity] = []
        values = self._det_sample_unique_sorted(s, config)
        n = max(len(values), 1)

        def pct_ratio() -> float:
            hits = 0
            for v in values:
                v = str(v).strip()
                if not v:
                    continue
                if _REG_PERCENT.match(v):
                    # numeric sanity 0-100
                    try:
                        num = float(v.replace("%", ""))
                        if 0 <= num <= 100:
                            hits += 1
                    except Exception:
                        pass
            return hits / n

        def currency_ratio() -> float:
            hits = 0
            for v in values:
                v_str = str(v).strip()
                if _REG_CURRENCY.match(v_str):
                    # Additional checks for currency
                    if any(c in v_str for c in ['$', '€', '£', '¥']):
                        hits += 1
                    elif any(word in column.name.lower() for word in ['price', 'cost', 'revenue', 'salary']):
                        hits += 1
            return hits / n

        def latlon_ratio(which: str) -> float:
            rx = _REG_LAT if which == "lat" else _REG_LON
            hits = 0
            for v in values:
                v_str = str(v).strip()
                # Skip if it looks like a year (4-digit number 1900-2100)
                if len(v_str) == 4 and v_str.isdigit() and 1900 <= int(v_str) <= 2100:
                    continue
                if rx.match(v_str):
                    hits += 1
            return hits / n

        def year_ratio() -> float:
            hits = 0
            for v in values:
                if _REG_YEAR.match(str(v).strip()):
                    hits += 1
            return hits / n

        # Create attribute for this column
        attribute = Attribute(
            name=column.name,
            data_type=column.data_type,
            source_column=column.name,
            confidence=1.0,
            statistics=column.statistics,
            sample_values=column.sample_values
        )

        # Percentage detection
        pr = pct_ratio()
        if pr >= 0.80:
            entity = Entity(
                name=column.name,
                entity_type=EntityType.PERCENTAGE.value,
                attributes=[attribute],
                confidence=float(pr),
                source_table=self.current_file_path
            )
            entity.id = self._generate_entity_id(entity)
            out.append(entity)

        # Currency detection
        cr = currency_ratio()
        if cr >= 0.80:
            entity = Entity(
                name=column.name,
                entity_type=EntityType.CURRENCY.value,
                attributes=[attribute],
                confidence=float(cr),
                source_table=self.current_file_path
            )
            entity.id = _stable_hash_text(f"{column.name}_{EntityType.CURRENCY.value}")[:12]
            out.append(entity)

        # Latitude/Longitude detection
        latr = latlon_ratio("lat")
        lonr = latlon_ratio("lon")
        if latr >= 0.80:
            entity = Entity(
                name=column.name,
                entity_type=EntityType.LATITUDE.value,
                attributes=[attribute],
                confidence=float(latr),
                source_table=self.current_file_path
            )
            entity.id = self._generate_entity_id(entity)
            out.append(entity)
        if lonr >= 0.80:
            entity = Entity(
                name=column.name,
                entity_type=EntityType.LONGITUDE.value,
                attributes=[attribute],
                confidence=float(lonr),
                source_table=self.current_file_path
            )
            entity.id = self._generate_entity_id(entity)
            out.append(entity)

        # Year detection
        yr = year_ratio()
        # Check if column name is a year (4-digit number 1900-2100)
        is_year_column = (len(column.name) == 4 and column.name.isdigit() and 
                         1900 <= int(column.name) <= 2100)
        
        if yr >= 0.90 or is_year_column or any(k in column.name.lower() for k in ("year", "yr")):
            entity = Entity(
                name=column.name,
                entity_type=EntityType.YEAR.value,
                attributes=[attribute],
                confidence=float(max(0.7, yr)) if yr > 0 else 0.9,
                source_table=self.current_file_path
            )
            entity.id = self._generate_entity_id(entity)
            out.append(entity)
        return out

    # ---------- Generic Two-Entity Extraction ----------
    def _extract_semantic_entities(
        self, df: pd.DataFrame, columns: list[ColumnProfile], config: dict[str, Any]
    ) -> list[Entity]:
        """Extract semantically meaningful entities based on data patterns and structure."""
        entities: list[Entity] = []
        
        # Analyze dataset context to infer business meaning (including filename insights)
        dataset_context = self._analyze_dataset_context(df, columns, self.current_file_path)
        
        # Handle different types of multi-entity datasets
        if self._is_multi_entity_dataset(columns):
            if self._is_time_series_dataset(columns):
                return self._extract_time_series_entities(df, columns, config, dataset_context)
            else:
                return self._extract_relational_entities(df, columns, config, dataset_context)
        
        # Special handling for time-series datasets with entity keys (legacy - will be removed)
        if self._is_time_series_dataset(columns):
            # This is a time-series dataset where each row is an entity with measurements over time
            # Example: countries with employment percentages over years
            
            # First column is usually the entity identifier (e.g., country, product, etc.)
            first_col = columns[0]
            first_col_name_lower = first_col.name.lower()
            
            # Create entity from the identifier column
            if first_col.data_type == DataType.STRING:
                # Use the new LLM-based entity naming approach
                entity_name = self._infer_meaningful_entity_name(self.current_file_path, columns, config)
                entity_type = self._determine_entity_type(entity_name, columns)
                
                # Create entity with the identifier as attribute
                attribute = Attribute(
                    name=first_col.name,
                    data_type=first_col.data_type,
                    source_column=first_col.name,
                    confidence=0.95,
                    statistics=first_col.statistics,
                    sample_values=first_col.sample_values
                )
                
                entity = Entity(
                    name=entity_name,
                    entity_type=entity_type,
                    attributes=[attribute],
                    confidence=0.95,
                    source_table=self.current_file_path
                )
                entity.id = self._generate_entity_id(entity)
                entities.append(entity)
                logger.info(f"Created {entity_type} entity '{entity_name}' from identifier column '{first_col.name}'")
                
                # Now handle the time-series measurements
                time_cols = []
                for col in columns[1:]:  # Skip the first column (entity identifier)
                    if self._is_time_column(col.name):
                        time_cols.append(col)
                
                if time_cols:
                    # Create a measurement entity for the time-series data
                    measurement_name = self._infer_measurement_name_from_filename(self.current_file_path, columns)
                    
                    # Create attributes for all time columns
                    attributes = []
                    for col in time_cols:
                        attribute = Attribute(
                            name=col.name,
                            data_type=col.data_type,
                            source_column=col.name,
                            confidence=0.90,
                            statistics=col.statistics,
                            sample_values=col.sample_values
                        )
                        attributes.append(attribute)
                    
                    entity = Entity(
                        name=measurement_name,
                        entity_type=EntityType.MEASUREMENT.value,
                        attributes=attributes,
                        confidence=0.90,
                        source_table=self.current_file_path
                    )
                    entity.id = self._generate_entity_id(entity)
                    entities.append(entity)
                    logger.info(f"Created measurement entity '{measurement_name}' from {len(time_cols)} time-series columns")
                
                return entities
        
        # Regular semantic extraction for non-time-series data
        # Group string/categorical columns
        string_cols = []
        for col in columns:
            if col.data_type == DataType.STRING:
                string_cols.append(col)
        
        # Create semantically meaningful entities from string columns
        for string_col in string_cols:
            unique_count = df[string_col.name].nunique()
            
            # Infer semantic meaning from column name and data
            entity_name, entity_type = self._infer_semantic_meaning(
                string_col.name, 
                string_col.data_type,
                string_col.sample_values,
                unique_count,
                dataset_context
            )
            
            # Create attribute for this column
            attribute = Attribute(
                name=string_col.name,
                data_type=string_col.data_type,
                source_column=string_col.name,
                confidence=0.95,
                statistics=string_col.statistics,
                sample_values=string_col.sample_values
            )
            
            entity = Entity(
                name=entity_name,
                entity_type=entity_type,
                attributes=[attribute],
                confidence=0.95,
                source_table=self.current_file_path
            )
            entity.id = self._generate_entity_id(entity)
            entities.append(entity)
            logger.info(f"Created {entity_type} entity '{entity_name}' from column '{string_col.name}'")
        
        # Group and analyze numeric columns
        numeric_cols = []
        for col in columns:
            if col.data_type in [DataType.FLOAT, DataType.INTEGER, DataType.NUMERICAL]:
                numeric_cols.append(col)
        
        # Create semantically meaningful entity from numeric columns
        if numeric_cols:
            # Analyze if numeric columns represent time series or measurements
            time_cols = []
            measure_cols = []
            
            for col in numeric_cols:
                if self._is_time_column(col.name):
                    time_cols.append(col)
                else:
                    measure_cols.append(col)
            
            # If we have many time-based columns, it's likely time series data
            if len(time_cols) > 5:
                # Infer what kind of measurement based on dataset context
                measurement_name = self._infer_measurement_name_from_filename(self.current_file_path, columns)
                
                # Create attributes for all time columns
                attributes = []
                for col in time_cols:
                    attribute = Attribute(
                        name=col.name,
                        data_type=col.data_type,
                        source_column=col.name,
                        confidence=0.90,
                        statistics=col.statistics,
                        sample_values=col.sample_values
                    )
                    attributes.append(attribute)
                
                entity = Entity(
                    name=measurement_name,
                    entity_type=EntityType.MEASUREMENT.value,
                    attributes=attributes,
                    confidence=0.90,
                    source_table=self.current_file_path
                )
                entity.id = self._generate_entity_id(entity)
                entities.append(entity)
                logger.info(f"Created measurement entity '{measurement_name}' from {len(time_cols)} time columns")
            
            # Handle non-time numeric columns
            for col in measure_cols:
                entity_name, entity_type = self._infer_semantic_meaning(
                    col.name,
                    col.data_type,
                    [],
                    col.unique_count,
                    dataset_context
                )
                
                # Create attribute for this column
                attribute = Attribute(
                    name=col.name,
                    data_type=col.data_type,
                    source_column=col.name,
                    confidence=0.85,
                    statistics=col.statistics,
                    sample_values=col.sample_values
                )
                
                entity = Entity(
                    name=entity_name,
                    entity_type=entity_type,
                    attributes=[attribute],
                    confidence=0.85,
                    source_table=self.current_file_path
                )
                entity.id = self._generate_entity_id(entity)
                entities.append(entity)
                logger.info(f"Created {entity_type} entity '{entity_name}' from column '{col.name}'")
        
        logger.info(f"Final result: {len(entities)} semantically meaningful entities extracted")
        return entities

    def _analyze_dataset_context(self, df: pd.DataFrame, columns: list[ColumnProfile], file_path: str = None) -> dict[str, Any]:
        """Analyze the dataset to understand its business context using hybrid approach."""
        context = {
            "has_geographic_data": False,
            "has_time_series": False,
            "has_percentage_data": False,
            "has_financial_data": False,
            "primary_measurement_type": "generic",
            "column_patterns": {},
            "domain_context": "generic",
            "measurement_context": "generic"
        }
        
        # Extract insights from filename if available
        if file_path:
            filename_insights = self._extract_filename_insights(file_path)
            context.update(filename_insights)
        
        # Step 1: Try LLM domain detection if available
        if self.llm_manager and context["domain_context"] == "generic":
            detected_domain = self._llm_detect_domain(columns)
            if detected_domain != "generic":
                context["domain_context"] = detected_domain
                logger.info(f"LLM detected domain: {detected_domain}")
        
        # Step 2: Rule-based detection as fallback or validation
        if context["domain_context"] == "generic":
            # Check for healthcare data
            healthcare_keywords = ['patient', 'medical', 'health', 'hospital', 'readmission', 
                                  'diagnosis', 'treatment', 'clinical']
            for col in columns:
                col_lower = col.name.lower()
                if any(keyword in col_lower for keyword in healthcare_keywords):
                    context["domain_context"] = "healthcare"
                    break
        
        # Check for geographic columns
        geo_keywords = ['country', 'region', 'state', 'city', 'location', 'geo', 'area']
        for col in columns:
            col_lower = col.name.lower()
            if any(keyword in col_lower for keyword in geo_keywords):
                context["has_geographic_data"] = True
                context["column_patterns"][col.name] = "geographic"
        
        # Check for time series (year columns)
        year_cols = [col for col in columns if self._is_time_column(col.name)]
        if len(year_cols) > 3:
            context["has_time_series"] = True
        
        # Check data values for percentages
        for col in columns:
            if col.data_type in [DataType.FLOAT, DataType.NUMERICAL]:
                sample_vals = df[col.name].dropna().head(100)
                if len(sample_vals) > 0:
                    if (sample_vals >= 0).all() and (sample_vals <= 100).all():
                        context["has_percentage_data"] = True
                        break
        
        # Check for financial data
        financial_keywords = ['price', 'cost', 'revenue', 'profit', 'salary', 'expense']
        for col in columns:
            col_lower = col.name.lower()
            if any(keyword in col_lower for keyword in financial_keywords):
                context["has_financial_data"] = True
                break
        
        # Infer primary measurement type from data patterns
        if context["has_percentage_data"]:
            context["primary_measurement_type"] = "percentage"
        elif context["has_financial_data"]:
            context["primary_measurement_type"] = "financial"
        
        return context
    
    def _extract_filename_insights(self, file_path: str) -> dict[str, Any]:
        """Extract semantic insights from the filename."""
        from pathlib import Path
        
        filename = Path(file_path).stem.lower()  # Remove extension and convert to lowercase
        insights = {
            "domain_context": "generic",
            "measurement_context": "generic",
            "subject_matter": None,
            "metric_type": None
        }
        
        # Domain/Industry patterns
        domain_patterns = {
            "healthcare": ["patient", "medical", "health", "hospital", "readmission", 
                          "diagnosis", "treatment", "clinical"],
            "finance": ["finance", "financial", "revenue", "profit", "investment", "banking"],
            "education": ["education", "school", "student", "academic", "university", "learning"],
            "retail": ["retail", "sales", "customer", "product", "inventory", "store"],
        }
        
        # Measurement type patterns
        measurement_patterns = {
            "percentage": ["percent", "percentage", "rate", "ratio", "_pct", "share"],
            "count": ["count", "number", "total", "quantity", "amount"],
            "financial": ["revenue", "cost", "price", "salary", "wage", "income", "expense"],
            "time_based": ["daily", "monthly", "yearly", "annual", "quarterly", "weekly"],
            "performance": ["performance", "efficiency", "productivity", "score", "rating"],
        }
        
        # Analyze filename for patterns
        for domain, keywords in domain_patterns.items():
            if any(keyword in filename for keyword in keywords):
                insights["domain_context"] = domain
                logger.info(f"Detected domain context from filename: {domain}")
                break
        
        for measurement_type, keywords in measurement_patterns.items():
            if any(keyword in filename for keyword in keywords):
                insights["measurement_context"] = measurement_type
                logger.info(f"Detected measurement context from filename: {measurement_type}")
                break
        
        return insights
    
    def _is_time_column(self, col_name: str) -> bool:
        """Check if a column name represents a time dimension."""
        # Check if it's a year (4 digits between 1900-2100)
        if col_name.isdigit() and len(col_name) == 4:
            year = int(col_name)
            return 1900 <= year <= 2100
        
        # Check for other time patterns
        time_keywords = ['year', 'month', 'date', 'time', 'quarter', 'period']
        return any(keyword in col_name.lower() for keyword in time_keywords)
    
    def _infer_semantic_meaning(
        self, 
        col_name: str, 
        data_type: DataType,
        sample_values: list,
        unique_count: int,
        context: dict[str, Any]
    ) -> tuple[str, str]:
        """Infer semantic meaning from column characteristics."""
        col_lower = col_name.lower()
        domain = context.get("domain_context", "generic")
        
        # Check domain-specific patterns first
        if domain in self.domain_patterns:
            for entity_type, patterns in self.domain_patterns[domain].items():
                if any(pattern in col_lower for pattern in patterns):
                    # Create a meaningful name
                    entity_name = col_name.replace('_', ' ').title()
                    return entity_name, EntityType[entity_type.upper()].value if hasattr(EntityType, entity_type.upper()) else entity_type
        
        # Geographic entities
        if any(geo in col_lower for geo in ['country', 'nation', 'state', 'region']):
            return "Geographic Region", EntityType.REGION.value
        elif any(geo in col_lower for geo in ['city', 'town', 'location']):
            return "Location", EntityType.CITY.value
        
        # Identifier patterns
        if 'id' in col_lower or col_lower.endswith('_id'):
            return f"{col_name} Identifier", EntityType.IDENTIFIER.value
        
        # Category patterns
        if any(cat in col_lower for cat in ['type', 'category', 'class', 'group']):
            return f"{col_name} Category", EntityType.CATEGORY.value
        
        # Status patterns
        if any(status in col_lower for status in ['status', 'state', 'condition']):
            return f"{col_name} Status", EntityType.STATUS.value
        
        # Default: Create meaningful name from column
        if data_type == DataType.STRING:
            # Capitalize and clean up column name
            entity_name = col_name.replace('_', ' ').replace('-', ' ').title()
            return entity_name, EntityType.CATEGORICAL.value
        else:
            return f"{col_name} Measurement", EntityType.MEASUREMENT.value
    
    def _infer_measurement_name_from_filename(self, file_path: str, columns: list[ColumnProfile] = None) -> str:
        """Infer a meaningful measurement name using LLM-driven approach."""
        from pathlib import Path
        
        filename = Path(file_path).stem.lower()
        
        # Try LLM first if available (truly scalable)
        if self.llm_manager and columns:
            measurement_name = self._llm_infer_measurement_name(filename, columns)
            if measurement_name and measurement_name != "Time Series Measurement":
                logger.info(f"LLM inferred measurement name: {measurement_name}")
                return measurement_name
        
        # Fallback: Simple heuristics only when LLM unavailable
        parts = filename.replace('_', ' ').replace('-', ' ').split()
        
        # Remove common noise words
        noise_words = ['data', 'dataset', 'table', 'csv', 'export', 'import', 'sample', 'test', 'demo', 
                       'of', 'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'with', 'by']
        meaningful_parts = [p for p in parts if p not in noise_words]
        
        # Look for measurement indicators
        if 'percent' in meaningful_parts or 'percentage' in meaningful_parts:
            # Remove percent/percentage and use the rest
            meaningful_parts = [p for p in meaningful_parts if p not in ['percent', 'percentage']]
            if meaningful_parts:
                # Generic approach: Take the most relevant measurement term
                # For long filenames, focus on the core measurement concept (last 1-2 words)
                if len(meaningful_parts) > 2:
                    # Take the last meaningful part as the core measurement
                    core_measurement = meaningful_parts[-1]
                    return f'{core_measurement.title()} Percentage'
                else:
                    return ' '.join(meaningful_parts).title() + ' Percentage'
        
        if 'rate' in meaningful_parts:
            meaningful_parts = [p for p in meaningful_parts if p != 'rate']
            if meaningful_parts:
                return ' '.join(meaningful_parts).title() + ' Rate'
        
        if 'count' in meaningful_parts:
            meaningful_parts = [p for p in meaningful_parts if p != 'count']
            if meaningful_parts:
                return ' '.join(meaningful_parts).title() + ' Count'
        
        # Default: use the cleaned up filename
        if meaningful_parts:
            return ' '.join(meaningful_parts).title()
        
        return 'Time Series Measurement'
    
    def _llm_infer_measurement_name(self, filename: str, columns: list[ColumnProfile]) -> str:
        """Use LLM to infer measurement name from filename and data structure."""
        if not self.llm_manager:
            return "Time Series Measurement"
        
        # Check cache first
        cache_content = f"{filename}_{[c.name for c in columns[:10]]}"
        cache_key = self._llm_cache_key("measurement_name", cache_content)
        
        if cached := self._get_llm_cached(cache_key):
            return cached["name"]
        
        # Prepare column info
        column_info = []
        for col in columns[:10]:  # Limit to first 10 columns for context
            col_info = f"- {col.name} ({col.data_type.value})"
            if col.sample_values and len(col.sample_values) > 0:
                samples = str(col.sample_values[:3])
                col_info += f" samples: {samples}"
            column_info.append(col_info)
        
        prompt = f"""Analyze this time-series dataset and determine what measurement it represents.

Dataset: {filename}
Columns:
{chr(10).join(column_info)}

This appears to be time-series data where each row represents an entity (like countries, products, etc.) 
and the columns represent measurements over time.

What type of measurement does this dataset track? Examples:
- Employment percentages over time
- GDP values by year  
- Temperature readings by month
- Sales revenue by quarter
- Population counts by decade

Return a JSON with:
{{
  "measurement_name": "descriptive name like 'Employment Percentage' or 'GDP Growth' or 'Temperature Reading'",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Be specific and descriptive. Avoid generic names like "Measurement" or "Data".
"""
        
        try:
            response = self.llm_manager.complete(prompt, temperature=0, response_format={"type": "json_object"})
            result = json.loads(response) if isinstance(response, str) else response
            
            measurement_name = result.get("measurement_name", "Time Series Measurement")
            
            # Cache the result
            self._save_llm_cache(cache_key, {"name": measurement_name})
            
            logger.info(f"LLM inferred measurement name: '{measurement_name}'")
            return measurement_name
            
        except Exception as e:
            logger.warning(f"LLM measurement name inference failed: {e}")
            return "Time Series Measurement"
    
    def _infer_measurement_type(
        self, 
        context: dict[str, Any], 
        df: pd.DataFrame,
        time_cols: list[ColumnProfile]
    ) -> str:
        """Infer the type of measurement from data patterns and filename context."""
        
        # Use filename insights for more specific measurement names
        domain = context.get("domain_context", "generic")
        measurement_context = context.get("measurement_context", "generic")
        
        # Sample some data to understand the measurement
        if time_cols:
            sample_col = time_cols[0].name
            sample_data = df[sample_col].dropna().head(100)
            
            # Check if it's percentage data
            if len(sample_data) > 0:
                if (sample_data >= 0).all() and (sample_data <= 100).all():
                    # Check for decimal values suggesting percentages
                    if (sample_data % 1 != 0).any():
                        # Use domain context for percentage measurements
                        if domain == "healthcare":
                            return "Health Metrics Percentage"
                        elif domain == "finance":
                            return "Financial Performance Percentage"
                        else:
                            return "Percentage Measurement"
            
            # Check value ranges for other measurement types
            if (sample_data < 0).any():
                return f"{domain.title()} Value Measurement" if domain != "generic" else "Value Measurement"
            elif (sample_data > 1000000).any():
                return f"{domain.title()} Count Measurement" if domain != "generic" else "Count Measurement"
            elif context.get("has_percentage_data"):
                return f"{domain.title()} Rate Measurement" if domain != "generic" else "Rate Measurement"
        
        # Default based on context with domain awareness
        if context.get("primary_measurement_type") == "percentage":
            return f"{domain.title()} Percentage" if domain != "generic" else "Percentage Measurement"
        elif context.get("primary_measurement_type") == "financial":
            return f"{domain.title()} Financial Measurement" if domain != "generic" else "Financial Measurement"
        else:
            return f"{domain.title()} Measurement" if domain != "generic" else "Metric Measurement"

    # ---------- Gate A: Basic categorical detection ----------
    def _extract_categorical_entities(
        self, s: pd.Series, column: ColumnProfile, config: dict[str, Any]
    ) -> list[Entity]:
        """Detect basic categorical entities (generic, no domain knowledge)."""
        out: list[Entity] = []
        values = self._det_sample_unique_sorted(s, config)
        n = max(len(values), 1)

        # Create attribute for this column
        attribute = Attribute(
            name=column.name,
            data_type=column.data_type,
            source_column=column.name,
            confidence=0.8,
            statistics=column.statistics,
            sample_values=column.sample_values
        )

        # Simple categorical detection based on data characteristics only
        if column.data_type == DataType.STRING and len(values) > 0:
            # Check if this looks like a categorical column
            unique_ratio = len(values) / max(len(s.dropna()), 1)
            
            # If we have reasonable number of categories (not too many, not too few)
            if 2 <= len(values) <= 1000 and unique_ratio < 0.8:
                entity = Entity(
                    name=column.name,
                    entity_type=EntityType.CATEGORICAL.value,
                    attributes=[attribute],
                    confidence=0.8,
                    source_table=self.current_file_path
                )
                entity.id = self._generate_entity_id(entity)
                out.append(entity)

        return out

    # ---------- Gate C: LLM (last resort, deterministic & cached) ----------
    def _extract_llm_entities(
        self, s: pd.Series, column: ColumnProfile, config: dict[str, Any]
    ) -> list[Entity]:
        if not self.llm_manager:
            return []
        sample = self._det_sample_unique_sorted(s, config)
        prompt = self._prompt_for_column(column, sample)
        key = _stable_hash_text(prompt)

        cache = self._cache_path(f"llm_{key}")
        if cache and cache.exists():
            try:
                raw = json.loads(cache.read_text())
                return [Entity(**e) for e in raw]
            except Exception:
                pass

        # Deterministic decode
        kwargs = {"temperature": 0.0, "top_p": 1.0}
        try:
            kwargs["seed"] = 42
        except Exception:
            pass

        # Expect the LLM manager to respect schema/enum if it supports it
        results = self.llm_manager.extract_entities_for_column(
            prompt=prompt,
            column_name=column.name,
            allowed_types=[t.value for t in EntityType],
            **kwargs,
        )

        entities: list[Entity] = []
        for r in results or []:
            try:
                # Create attribute for this column
                attribute = Attribute(
                    name=column.name,
                    data_type=column.data_type,
                    source_column=column.name,
                    confidence=float(r.get("confidence", 0.6)),
                    statistics=column.statistics,
                    sample_values=column.sample_values
                )
                
                entities.append(
                    Entity(
                        name=column.name,
                        entity_type=str(r.get("entity_type", EntityType.UNKNOWN.value)),
                        attributes=[attribute],
                        confidence=float(r.get("confidence", 0.6)),
                        source_table=self.current_file_path
                    )
                )
            except Exception as e:
                logger.debug(f"LLM row skipped: {e}")

        if cache:
            try:
                cache.write_text(
                    json.dumps([e.model_dump() for e in entities], ensure_ascii=False)
                )
            except Exception:
                pass
        return entities

    def _extract_business_entities_llm(
        self,
        df: pd.DataFrame,
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Entity]:
        if not self.llm_manager:
            return []
        # Small, deterministic context: schema + few representative rows
        sample_rows = df.head(int(_safe_config_get(config, "llm_context_rows", 20))).to_dict(
            orient="records"
        )
        context = {
            "columns": [c.name for c in columns],
            "dtypes": {c.name: str(c.data_type) for c in columns},
            "sample_rows": sample_rows,
        }
        prompt = self._prompt_for_business_entities(context)
        key = _stable_hash_text(prompt)
        cache = self._cache_path(f"llm_business_{key}")
        if cache and cache.exists():
            try:
                raw = json.loads(cache.read_text())
                return [Entity(**e) for e in raw]
            except Exception:
                pass

        kwargs = {"temperature": 0.0, "top_p": 1.0}
        try:
            kwargs["seed"] = 42
        except Exception:
            pass

        results = self.llm_manager.identify_business_entities(
            prompt=prompt,
            **kwargs,
        )
        entities: list[Entity] = []
        for r in results or []:
            try:
                name = r.get("name") or r.get("column") or "business_entity"
                
                # Create attributes for all source columns
                attributes = []
                for col_name in r.get("source_columns", []):
                    # Find the column profile
                    col_profile = next((c for c in columns if c.name == col_name), None)
                    if col_profile:
                        attribute = Attribute(
                            name=col_name,
                            data_type=col_profile.data_type,
                            source_column=col_name,
                            confidence=float(r.get("confidence", 0.6)),
                            statistics=col_profile.statistics,
                            sample_values=col_profile.sample_values
                        )
                        attributes.append(attribute)
                
                entities.append(
                    Entity(
                        name=name,
                        entity_type=str(r.get("entity_type", EntityType.UNKNOWN.value)),
                        attributes=attributes,
                        confidence=float(r.get("confidence", 0.6)),
                        source_table=self.current_file_path
                    )
                )
            except Exception:
                pass
        if cache:
            try:
                cache.write_text(
                    json.dumps([e.model_dump() for e in entities], ensure_ascii=False)
                )
            except Exception:
                pass
        return entities

    # ---------- selection: pick best entity per column ----------
    def _choose_best_entity(
        self, entities: list[Entity], column: ColumnProfile, config: dict[str, Any]
    ) -> Entity:
        name = column.name.lower()

        def name_prior(e: Entity) -> float:
            t = e.entity_type.lower()
            score = 0.0
            if "id" in name and "id" in t:
                score += 0.1
            if any(k in name for k in ("date", "dt", "year", "yr")) and t in (
                "date",
                "time",
                "time_dimension",
            ):
                score += 0.1
            if (
                any(k in name for k in ("pct", "percent", "rate", "%"))
                and t == "measurement"
            ):
                score += 0.1
            if any(k in name for k in ("lat", "latitude")) and t.startswith(
                "location_lat"
            ):
                score += 0.1
            if any(k in name for k in ("lon", "lng", "longitude")) and t.startswith(
                "location_lon"
            ):
                score += 0.1
            if any(k in name for k in ("zip", "postal")) and t in (
                "postal_code",
                "address",
            ):
                score += 0.1
            return score

        def pri_idx(e: Entity) -> int:
            try:
                return self.entity_priority.index(e.entity_type)
            except ValueError:
                return len(self.entity_priority)

        ranked = sorted(
            entities,
            key=lambda e: (
                -(float(getattr(e, "confidence", 0.0)) + name_prior(e)),
                pri_idx(e),
            ),
        )
        return ranked[0]

    # ---------- consolidation: dedup by meaning ----------
    def _deduplicate_by_embeddings(
        self, entities: list[Entity], config: dict[str, Any]
    ) -> list[Entity]:
        if not entities:
            return entities
        thr = float(_safe_config_get(config, "dedup_similarity_threshold", 0.90))
        if not self.embeddings:
            # basic textual dedup (exact same signature)
            seen = set()
            out: list[Entity] = []
            for e in entities:
                sig = (e.name, e.entity_type, e.source_table)
                if sig in seen:
                    continue
                seen.add(sig)
                out.append(e)
            return out

        # With embeddings: cluster by cosine sim >= thr
        vecs = self.embeddings.encode(
            [self._entity_signature_text(e) for e in entities]
        )
        used = [False] * len(entities)
        clusters: list[list[int]] = []
        for i in range(len(entities)):
            if used[i]:
                continue
            cluster = [i]
            used[i] = True
            for j in range(i + 1, len(entities)):
                if used[j]:
                    continue
                sim = self.embeddings.cosine_similarity(vecs[i], vecs[j])
                if sim >= thr:
                    used[j] = True
                    cluster.append(j)
            clusters.append(cluster)

        # Merge per cluster by picking highest confidence
        merged: list[Entity] = []
        for idxs in clusters:
            cand = max(
                (entities[k] for k in idxs),
                key=lambda e: float(getattr(e, "confidence", 0.0)),
            )
            merged.append(cand)
        return merged

    @staticmethod
    def _entity_signature_text(e: Entity) -> str:
        return f"{e.name}|{e.entity_type}|{e.source_table}"

    # ---------- prompts ----------
    @staticmethod
    def _prompt_for_column(column: ColumnProfile, sample_values: list[str]) -> str:
        allowed = [t.value for t in EntityType]
        return (
            "You are an ontology-aware extractor.\n"
            "Decide the SINGLE best entity_type for the column below from the allowed set.\n"
            f"Allowed types: {allowed}.\n"
            "Return strict JSON with keys: entity_type, confidence (0-1), reason.\n\n"
            f"Column name: {column.name}\n"
            f"Data type hint: {column.data_type}\n"
            f"Samples (sorted unique subset): {sample_values[:50]}\n"
        )

    @staticmethod
    def _prompt_for_business_entities(context: dict[str, Any]) -> str:
        return (
            "Identify core entities from the dataset based on data structure patterns only.\n"
            "Return JSON list with objects: {name, entity_type, source_columns, confidence, reason}.\n"
            f"Use these entity types: {[t.value for t in EntityType]}.\n"
            "Base decisions on data patterns, not domain knowledge.\n"
            f"Context: {json.dumps(context, ensure_ascii=False)[:4000]}"
        )

    # ---------- IO & sampling ----------
    @staticmethod
    def _safe_read_csv(
        path: str | Path, usecols: list[str] | None = None
    ) -> pd.DataFrame:
        df = pd.read_csv(path, usecols=usecols, low_memory=False)
        return df

    @staticmethod
    def _det_sample_unique_sorted(s: pd.Series, config: dict[str, Any]) -> list[str]:
        maxn = int(_safe_config_get(config, "max_entities_per_column", 200))
        vals = (
            s.dropna()
            .astype(str)
            .map(lambda x: x.strip())
            .replace({"": np.nan})
            .dropna()
            .unique()
            .tolist()
        )
        # deterministic sort
        vals = sorted(vals)
        if len(vals) > maxn:
            vals = vals[:maxn]
        return vals

# ---------- Factory Functions ----------
def create_entity_extractor(
    cache_dir: str | Path | None = ".cache/entity_extractor",
    llm_manager: Any | None = None,
    embeddings_manager: Any | None = None,
    use_langgraph: bool = True,
    force_langgraph: bool = False,
) -> EntityExtractor | LangGraphEntityExtractor:
    """Factory function to create the appropriate entity extractor.
    
    Args:
        cache_dir: Cache directory path
        llm_manager: LLM manager instance
        embeddings_manager: Embeddings manager instance
        use_langgraph: Whether to prefer LangGraph if available
        force_langgraph: Force LangGraph usage (raises error if not available)
        
    Returns:
        EntityExtractor or LangGraphEntityExtractor instance
        
    Raises:
        ImportError: If force_langgraph=True but LangGraph is not available
    """
    if force_langgraph and not LANGGRAPH_AVAILABLE:
        raise ImportError("LangGraph is required but not available. Install with: pip install langgraph")
    
    if force_langgraph:
        return LangGraphEntityExtractor(
            cache_dir=cache_dir,
            llm_manager=llm_manager,
            embeddings_manager=embeddings_manager
        )
    
    # Default: Try LangGraph through EntityExtractor with fallback
    return EntityExtractor(
        cache_dir=cache_dir,
        llm_manager=llm_manager,
        embeddings_manager=embeddings_manager,
        use_langgraph=use_langgraph
    )

# -------------
# End of file.
# -------------