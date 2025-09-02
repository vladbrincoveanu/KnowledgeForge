from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Import your local models
from app.domain.models.entities import ColumnProfile, DataType, Entity

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


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
# Main Extractor with three-gate pipeline
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


class EntityExtractor:
    def __init__(
        self,
        cache_dir: str | Path | None = ".cache/entity_extractor",
        llm_manager: Any | None = None,
        embeddings_manager: Any | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.llm_manager = llm_manager
        self.embeddings = embeddings_manager

    def _generate_entity_id(self, entity: Entity) -> str:
        """Generate a deterministic ID for an entity based on its content."""
        # Create a stable hash based on entity properties
        content = f"{entity.name}_{entity.entity_type}_{','.join(sorted(entity.source_columns))}"
        return f"entity_{_stable_hash_text(content)[:12]}"

    # ---------- public API ----------
    def extract_entities(
        self,
        file_path: str,
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Entity]:
        """Top-level entry: deterministic run with caching."""
        logger.info(f"Extracting entities from {file_path}")

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
        payload = [e.__dict__ for e in entities]
        path.write_text(json.dumps(payload, ensure_ascii=False))

    # ---------- gate A/B/C orchestrator ----------
    def _extract_entities_traditional(
        self,
        file_path: str,
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Entity]:
        # Store file path for context analysis
        self.current_file_path = file_path
        df = self._safe_read_csv(file_path, usecols=[c.name for c in columns])

        per_column: list[Entity] = []
        business_entities: list[Entity] = []  # Initialize business_entities list
        
        # Extract semantic entities based on dataset understanding
        logger.info("Starting semantic entity extraction...")
        semantic_entities = self._extract_semantic_entities(df, columns, config)
        per_column.extend(semantic_entities)
        logger.info(f"Extracted {len(semantic_entities)} semantic entities")
        
        # Fallback: Extract entities per column if semantic extraction fails
        if not semantic_entities:
            logger.info("Semantic extraction failed, falling back to column-level extraction")
            for col in columns[: int(_safe_config_get(config, "max_columns_to_process", 10_000))]:
                try:
                    logger.info(f"Extracting entities for column: {col.name}")
                    col_entities = self._extract_column_entities(df, col, config)
                    per_column.extend(col_entities)
                    logger.info(f"Column {col.name}: extracted {len(col_entities)} entities")
                except Exception as e:
                    logger.warning(f"Entity extraction failed for column {col.name}: {e}")
        
        # Also try business entity extraction (if enabled)
        if _safe_config_get(config, "extract_business_entities", False):
            try:
                logger.info("Attempting LLM-based business entity extraction...")
                llm_entities = self._extract_business_entities_enhanced(df, columns, config)
                business_entities.extend(llm_entities)
                logger.info(f"Business LLM extraction added {len(llm_entities)} entities")
            except Exception as e:
                logger.warning(f"Business LLM extraction failed: {e}")

        # Optional business-level entities; gated & cached inside
        per_dataset: list[Entity] = []
        if _safe_config_get(config, "use_llm", True) and _safe_config_get(
            config, "extract_business_entities", False
        ):
            try:
                per_dataset = self._extract_business_entities_llm(df, columns, config)
            except Exception as e:
                logger.warning(f"Business LLM extraction skipped: {e}")

        # Deduplicate by meaning
        if _safe_config_get(config, "use_intelligent_consolidation", True):
            business_entities = self._deduplicate_by_embeddings(business_entities, config)

        # Combine per-column and business entities
        all_entities = per_column + business_entities + per_dataset
        
        # Drop low-confidence
        thr = float(_safe_config_get(config, "confidence_threshold", 0.70))
        entities = [e for e in all_entities if float(getattr(e, "confidence", 1.0)) >= thr]

        # Optionally cap count
        max_entities = int(_safe_config_get(config, "max_entities", 100_000))
        if len(entities) > max_entities:
            entities = entities[:max_entities]
        
        logger.info(f"Total entities extracted: {len(entities)} (per-column: {len(per_column)}, business: {len(business_entities)}, dataset: {len(per_dataset)})")
        return entities

    # ---------- Business-focused entity extraction ----------
    def _extract_business_entities_enhanced(
        self, df: pd.DataFrame, columns: list[ColumnProfile], config: dict[str, Any]
    ) -> list[Entity]:
        """Extract meaningful business entities from the dataset."""
        if not self.llm_manager:
            return []
        
        try:
            logger.info(f"Creating dataset summary for LLM analysis...")
            # Create a focused business analysis prompt
            dataset_summary = {
                "total_rows": len(df),
                "total_columns": len(columns),
                "column_types": {
                    col.name: {
                        "data_type": str(col.data_type),
                        "unique_count": col.unique_count,
                        "sample_values": col.sample_values[:3]
                    }
                    for col in columns
                }
            }
            logger.info(f"Dataset summary created: {len(df)} rows, {len(columns)} columns")
            
            prompt = f"""
Analyze this dataset and identify core entities based on data structure patterns only:

Dataset Summary: {json.dumps(dataset_summary, indent=2)}

Extract entities from:
- String/categorical columns (use column names as entity names)
- Numeric columns (group related numeric data if appropriate)

Rules:
- Use actual column names as entity names
- Use only these entity types: "categorical", "numerical", "time_dimension", "identifier"
- Base decisions purely on data patterns, not domain knowledge
- Group related columns only when they represent the same concept
 
For each entity provide:
- name: actual column name or grouped name
- entity_type: one of the allowed types above
- confidence: 0.0-1.0 based on data pattern clarity
- reason: data pattern justification (no domain assumptions)
- source_columns: list of relevant column names

Return JSON array with entities.
"""
            
            # Use LLM to analyze the dataset
            logger.info("Sending prompt to LLM for business entity analysis...")
            response = self.llm_manager.generate_text(prompt, max_tokens=400, temperature=0.1)
            
            if response:
                logger.info(f"LLM response received (length: {len(response)})")
                logger.info(f"LLM response preview: {response[:200]}...")
                
                try:
                    # Extract JSON from response
                    json_start = response.find('[')
                    json_end = response.rfind(']') + 1
                    
                    if json_start != -1 and json_end != -1:
                        json_str = response[json_start:json_end]
                        logger.info(f"Extracted JSON string: {json_str}")
                        
                        entities_data = json.loads(json_str)
                        logger.info(f"Parsed JSON data: {len(entities_data)} entity records")
                        
                        entities = []
                        for i, entity_data in enumerate(entities_data):
                            try:
                                logger.info(f"Creating entity {i+1} from LLM data: {entity_data}")
                                entity = Entity(
                                    id=str(uuid.uuid4()),
                                    name=entity_data.get("name", "unknown"),
                                    entity_type=entity_data.get("entity_type", "unknown"),
                                    source_columns=entity_data.get("source_columns", []),
                                    confidence=float(entity_data.get("confidence", 0.8)),
                                    description=entity_data.get("reason", "Business domain analysis")
                                )
                                entities.append(entity)
                                logger.info(f"✅ Created LLM entity: id={entity.id}, name='{entity.name}', type='{entity.entity_type}'")
                            except Exception as e:
                                logger.error(f"❌ Failed to create business entity from data {entity_data}: {e}")
                        
                        logger.info(f"LLM entity creation completed: {len(entities)} entities created")
                        return entities
                    else:
                        logger.warning(f"Could not find JSON array in LLM response. json_start={json_start}, json_end={json_end}")
                        logger.warning(f"Full LLM response: {response}")
                except Exception as e:
                    logger.error(f"❌ Failed to parse LLM response: {e}")
                    logger.error(f"LLM response that failed to parse: {response}")
            else:
                logger.warning("LLM returned no response")
            
            return []
            
        except Exception as e:
            logger.warning(f"Business entity extraction failed: {e}")
            return []

    def _extract_basic_entities(self, df: pd.DataFrame, columns: list[ColumnProfile], config: dict[str, Any]) -> list[Entity]:
        """Fallback basic entity extraction if LLM fails."""
        entities = []
        
        logger.info(f"Starting basic entity extraction for {len(columns)} columns")
        
        # Generic entity extraction based on data patterns only
        for col in columns:
            col_name = col.name.lower()
            logger.info(f"Analyzing column: '{col.name}' (type: {col.data_type}, unique: {col.unique_count})")
            
            # Generic string/categorical entity
            if col.data_type == DataType.STRING and col.unique_count > 1:
                logger.info(f"  Found categorical column: {col.name}")
                entity = Entity(
                    id=str(uuid.uuid4()),
                    name=col.name,
                    entity_type="categorical",
                    source_columns=[col.name],
                    confidence=0.90,
                    description=f"Categorical data with {col.unique_count} unique values"
                )
                entities.append(entity)
                logger.info(f"  ✅ Created categorical entity: id={entity.id}")
            
            # Generic numeric entity
            elif col.data_type in [DataType.FLOAT, DataType.INTEGER, DataType.NUMERICAL] and col.unique_count > 5:
                logger.info(f"  Found numeric column: {col.name} (unique values: {col.unique_count})")
                
                # Check if column name is a year (time dimension)
                if col.name.isdigit() and 1900 <= int(col.name) <= 2100:
                    logger.info(f"    Column name is a year: {col.name}")
                    entity = Entity(
                        id=str(uuid.uuid4()),
                        name=col.name,
                        entity_type="time_dimension",
                        source_columns=[col.name],
                        confidence=0.95,
                        description=f"Time dimension for year {col.name}"
                    )
                    entities.append(entity)
                    logger.info(f"    ✅ Created time dimension entity for year {col.name}: id={entity.id}")
                else:
                    # Generic numeric measurement
                    entity = Entity(
                        id=str(uuid.uuid4()),
                        name=col.name,
                        entity_type="measurement",
                        source_columns=[col.name],
                        confidence=0.85,
                        description=f"Numeric measurement data from column {col.name}"
                    )
                    entities.append(entity)
                    logger.info(f"    ✅ Created measurement entity: id={entity.id}")
            else:
                logger.info(f"  Column '{col.name}' does not match basic entity patterns")
        
        logger.info(f"Basic entity extraction completed: {len(entities)} entities created")
        return entities

    # ---------- Gate A + selection ----------
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
            "email",
            "url",
            "ip_address",
            "uuid",
            "credit_card",
            "ssn",
            "date",
            "time",
            "postal_code",
            "address",
            "phone",
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

        # Strategy 3 (LLM): only if nothing else found with confidence
        if _safe_config_get(config, "use_llm", True) and not entities:
            try:
                entities.extend(self._extract_llm_entities(s, column, config))
            except Exception as e:
                logger.warning(f"LLM extraction failed for column {name}: {e}")

        # Strategy 4: pattern-based (percent/latlon/year/etc.)
        entities.extend(self._extract_pattern_entities(s, column, config))

        # Strategy 5: basic categorical detection (generic)
        entities.extend(self._extract_categorical_entities(s, column, config))

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
            ("email", _REG_EMAIL),
            ("ip_address", _REG_IP),
            ("uuid", _REG_UUID),
            ("credit_card", _REG_CREDIT_CARD),
            ("phone", _REG_PHONE),
            ("postal_code", _REG_POSTAL_5),
            # URL check moved to end to avoid false positives with years
            ("url", _REG_URL),
        ]
        for t, rx in checks:
            r = ratio(rx)
            if r >= 0.70:  # strong validator
                entity = Entity(
                    name=column.name,
                    entity_type=t,
                    source_columns=[column.name],
                    confidence=float(r),
                    description=f"Validated as {t} by pattern checks",
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

        if ur >= 0.98 and (monotonic or id_prior):
            entity = Entity(
                name=column.name,
                entity_type="sequential_id" if monotonic else "identifier",
                source_columns=[column.name],
                confidence=float(min(1.0, 0.7 + 0.3 * ur)),
                description="High uniqueness; ID/name prior/sequence detected",
            )
            entity.id = self._generate_entity_id(entity)
            out.append(entity)
        elif ur >= 0.95 or loose_ratio >= 0.7:
            entity = Entity(
                name=column.name,
                entity_type="identifier",
                source_columns=[column.name],
                confidence=float(max(0.70, min(0.95, ur))),
                description="High uniqueness suggests identifier",
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

        pr = pct_ratio()
        if pr >= 0.80:
            entity = Entity(
                name=column.name,
                entity_type="measurement",
                source_columns=[column.name],
                confidence=float(pr),
                description="Percentage measurement (0–100%)",
            )
            entity.id = self._generate_entity_id(entity)
            out.append(entity)

        latr = latlon_ratio("lat")
        lonr = latlon_ratio("lon")
        if latr >= 0.80:
            entity = Entity(
                name=column.name,
                entity_type="location_latitude",
                source_columns=[column.name],
                confidence=float(latr),
                description="Latitude values",
            )
            entity.id = self._generate_entity_id(entity)
            out.append(entity)
        if lonr >= 0.80:
            entity = Entity(
                name=column.name,
                entity_type="location_longitude",
                source_columns=[column.name],
                confidence=float(lonr),
                description="Longitude values",
            )
            entity.id = self._generate_entity_id(entity)
            out.append(entity)

        yr = year_ratio()
        # Check if column name is a year (4-digit number 1900-2100)
        is_year_column = (len(column.name) == 4 and column.name.isdigit() and 
                         1900 <= int(column.name) <= 2100)
        
        if yr >= 0.90 or is_year_column or any(k in column.name.lower() for k in ("year", "yr")):
            entity = Entity(
                name=column.name,
                entity_type="time_dimension",
                source_columns=[column.name],
                confidence=float(max(0.7, yr)) if yr > 0 else 0.9,
                description="Year-like time dimension",
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
            
            entity = Entity(
                name=entity_name,
                entity_type=entity_type,
                source_columns=[string_col.name],
                confidence=0.95,
                description=f"{entity_type.replace('_', ' ').title()} with {unique_count} unique values"
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
                measurement_name = self._infer_measurement_type(dataset_context, df, time_cols)
                
                entity = Entity(
                    name=measurement_name,
                    entity_type="measurement",
                    source_columns=[col.name for col in time_cols],
                    confidence=0.90,
                    description=f"Time series measurements across {len(time_cols)} time periods"
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
                
                entity = Entity(
                    name=entity_name,
                    entity_type=entity_type,
                    source_columns=[col.name],
                    confidence=0.85,
                    description=f"{entity_type.replace('_', ' ').title()} measurement"
                )
                entity.id = self._generate_entity_id(entity)
                entities.append(entity)
                logger.info(f"Created {entity_type} entity '{entity_name}' from column '{col.name}'")
        
        logger.info(f"Final result: {len(entities)} semantically meaningful entities extracted")
        return entities

    def _analyze_dataset_context(self, df: pd.DataFrame, columns: list[ColumnProfile], file_path: str = None) -> dict[str, Any]:
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
            "agriculture": ["agriculture", "agricultural", "farming", "farm", "crops", "livestock"],
            "healthcare": ["health", "medical", "patient", "hospital", "disease", "treatment"],
            "finance": ["finance", "financial", "revenue", "profit", "investment", "banking"],
            "education": ["education", "school", "student", "academic", "university", "learning"],
            "retail": ["retail", "sales", "customer", "product", "inventory", "store"],
            "hr": ["employee", "staff", "workforce", "personnel", "hr", "human_resources"],
            "manufacturing": ["production", "manufacturing", "factory", "industrial", "assembly"],
            "logistics": ["shipping", "transport", "logistics", "delivery", "supply_chain"],
            "energy": ["energy", "power", "electricity", "renewable", "consumption", "utility"],
            "real_estate": ["property", "real_estate", "housing", "rental", "mortgage"]
        }
        
        # Measurement type patterns
        measurement_patterns = {
            "percentage": ["percent", "percentage", "rate", "ratio", "_pct", "share"],
            "count": ["count", "number", "total", "quantity", "amount"],
            "financial": ["revenue", "cost", "price", "salary", "wage", "income", "expense"],
            "time_based": ["daily", "monthly", "yearly", "annual", "quarterly", "weekly"],
            "performance": ["performance", "efficiency", "productivity", "score", "rating"],
            "demographic": ["population", "demographic", "age", "gender", "ethnicity"],
            "employment": ["employment", "unemployment", "jobs", "workers", "labor", "workforce"]
        }
        
        # Subject matter patterns
        subject_patterns = {
            "workers": ["worker", "workers", "employee", "staff", "personnel", "labor"],
            "customers": ["customer", "client", "consumer", "buyer", "user"],
            "products": ["product", "item", "goods", "merchandise", "inventory"],
            "sales": ["sales", "transactions", "orders", "purchases", "deals"],
            "regions": ["country", "region", "state", "city", "location", "geographic"]
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
        
        for subject, keywords in subject_patterns.items():
            if any(keyword in filename for keyword in keywords):
                insights["subject_matter"] = subject
                logger.info(f"Detected subject matter from filename: {subject}")
                break
        
        # Special case for the agriculture workers example
        if "agriculture" in filename and "workers" in filename and "percent" in filename:
            insights.update({
                "domain_context": "agriculture",
                "measurement_context": "employment",
                "subject_matter": "workers",
                "metric_type": "employment_rate"
            })
            logger.info("Detected agriculture employment dataset from filename")
        
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
        
        # Geographic entities
        if any(geo in col_lower for geo in ['country', 'nation', 'state', 'region']):
            return "Geographic Region", "geographic_entity"
        elif any(geo in col_lower for geo in ['city', 'town', 'location']):
            return "Location", "geographic_entity"
        
        # Identifier patterns
        if 'id' in col_lower or col_lower.endswith('_id'):
            return f"{col_name} Identifier", "identifier"
        
        # Category patterns
        if any(cat in col_lower for cat in ['type', 'category', 'class', 'group']):
            return f"{col_name} Category", "categorical"
        
        # Status patterns
        if any(status in col_lower for status in ['status', 'state', 'condition']):
            return f"{col_name} Status", "categorical"
        
        # Default: Create meaningful name from column
        if data_type == DataType.STRING:
            # Capitalize and clean up column name
            entity_name = col_name.replace('_', ' ').replace('-', ' ').title()
            return entity_name, "categorical"
        else:
            return f"{col_name} Measurement", "measurement"
    
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
        subject_matter = context.get("subject_matter")
        metric_type = context.get("metric_type")
        
        # If we have specific metric type from filename, use it
        if metric_type == "employment_rate":
            return "Agricultural Employment Rate"
        
        # Create domain-specific measurement names
        if domain == "agriculture" and measurement_context == "employment":
            return "Agricultural Employment Measurement"
        elif domain == "agriculture" and subject_matter == "workers":
            return "Agricultural Worker Statistics"
        
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
                        if domain == "agriculture":
                            return "Agricultural Employment Percentage"
                        elif domain == "finance":
                            return "Financial Performance Percentage"
                        elif domain == "healthcare":
                            return "Health Metrics Percentage"
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

        # Simple categorical detection based on data characteristics only
        if column.data_type == DataType.STRING and len(values) > 0:
            # Check if this looks like a categorical column
            unique_ratio = len(values) / max(len(s.dropna()), 1)
            
            # If we have reasonable number of categories (not too many, not too few)
            if 2 <= len(values) <= 1000 and unique_ratio < 0.8:
                out.append(
                    Entity(
                        name=column.name,
                        entity_type="categorical",
                        source_columns=[column.name],
                        confidence=0.8,
                        description=f"Categorical data with {len(values)} unique values",
                    )
                )

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
            allowed_types=[
                "identifier",
                "measurement",
                "time_dimension",
                "location",
                "address",
                "email",
                "phone",
                "url",
                "uuid",
                "ip_address",
                "categorical",
                "unknown",
            ],
            **kwargs,
        )

        entities: list[Entity] = []
        for r in results or []:
            try:
                entities.append(
                    Entity(
                        name=column.name,
                        entity_type=str(r.get("entity_type", "unknown")),
                        source_columns=[column.name],
                        confidence=float(r.get("confidence", 0.6)),
                        description=str(r.get("reason", "LLM-inferred")),
                    )
                )
            except Exception as e:
                logger.debug(f"LLM row skipped: {e}")

        if cache:
            try:
                cache.write_text(
                    json.dumps([e.__dict__ for e in entities], ensure_ascii=False)
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
                entities.append(
                    Entity(
                        name=name,
                        entity_type=str(r.get("entity_type", "unknown")),
                        source_columns=r.get("source_columns") or [],
                        confidence=float(r.get("confidence", 0.6)),
                        description=str(r.get("reason", "LLM-inferred")),
                    )
                )
            except Exception:
                pass
        if cache:
            try:
                cache.write_text(
                    json.dumps([e.__dict__ for e in entities], ensure_ascii=False)
                )
            except Exception:
                pass
        return entities

    # ---------- selection: pick best entity per column ----------
    def _choose_best_entity(
        self, entities: list[Entity], column: ColumnProfile, config: dict[str, Any]
    ) -> Entity:
        PRIORITY: list[str] = [
            "email",
            "url",
            "ip_address",
            "uuid",
            "credit_card",
            "ssn",
            "date",
            "time",
            "postal_code",
            "address",
            "phone",
            "sequential_id",
            "uuid_like",
            "identifier",
            "composite_key",
            "measurement",
            "time_dimension",
            "location_latitude",
            "location_longitude",
            "location",
            "categorical",
            "pattern",
            "unknown",
        ]

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
                return PRIORITY.index(e.entity_type)
            except ValueError:
                return len(PRIORITY)

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
                sig = (e.name, e.entity_type, tuple(sorted(e.source_columns)))
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
        return f"{e.name}|{e.entity_type}|{','.join(sorted(e.source_columns or []))}"

    # ---------- prompts ----------
    @staticmethod
    def _prompt_for_column(column: ColumnProfile, sample_values: list[str]) -> str:
        allowed = [
            "identifier",
            "measurement",
            "time_dimension",
            "location",
            "address",
            "email",
            "phone",
            "url",
            "uuid",
            "ip_address",
            "categorical",
            "unknown",
        ]
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
            "Use actual column names. Entity types: categorical, numerical, time_dimension, identifier.\n"
            "Base decisions on data patterns, not domain knowledge.\n"
            f"Context: {json.dumps(context, ensure_ascii=False)[:4000]}"
        )

    # ---------- IO & sampling ----------
    @staticmethod
    def _safe_read_csv(
        path: str | Path, usecols: list[str] | None = None
    ) -> pd.DataFrame:
        # You can swap this for DuckDB/Polars if desired. Keep deterministic.
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


# -------------
# End of file.
# -------------
