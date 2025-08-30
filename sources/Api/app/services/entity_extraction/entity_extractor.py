from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import numpy as np
import re

# Import your local models
from app.domain.models.entities import ColumnProfile, Entity, DataType

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


# -----------------------
# Utility: Regex patterns
# -----------------------
_REG_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_REG_URL = re.compile(r"^(https?://)?([\w-]+\.)+[\w-]+(/\S*)?$")
_REG_IP = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
_REG_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
_REG_HEXISH_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
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

    # ---------- public API ----------
    def extract_entities(
        self,
        file_path: str,
        columns: List[ColumnProfile],
        config: Dict[str, Any],
    ) -> List[Entity]:
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
    def _cache_path(self, key: str, suffix: str = ".json") -> Optional[Path]:
        if not self.cache_dir:
            return None
        p = self.cache_dir / f"{key}{suffix}"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load_cached_entities(self, file_hash: str) -> Optional[List[Entity]]:
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
        payload = [e.__dict__ for e in entities]
        path.write_text(json.dumps(payload, ensure_ascii=False))

    # ---------- gate A/B/C orchestrator ----------
    def _extract_entities_traditional(
        self,
        file_path: str,
        columns: List[ColumnProfile],
        config: Dict[str, Any],
    ) -> List[Entity]:
        df = self._safe_read_csv(file_path, usecols=[c.name for c in columns])

        per_column: List[Entity] = []
        for col in columns[: int(config.get("max_columns_to_process", 10_000))]:
            try:
                per_column.extend(self._extract_column_entities(df, col, config))
            except Exception as e:
                logger.exception(f"Column {col.name} extraction failed: {e}")

        # Optional business-level entities; gated & cached inside
        per_dataset: List[Entity] = []
        if config.get("use_llm", True) and config.get("extract_business_entities", False):
            try:
                per_dataset = self._extract_business_entities_llm(df, columns, config)
            except Exception as e:
                logger.warning(f"Business LLM extraction skipped: {e}")

        entities = per_column + per_dataset

        # Deduplicate by meaning (configurable)
        if config.get("use_intelligent_consolidation", True):
            entities = self._deduplicate_by_embeddings(entities, config)

        # Drop low-confidence
        thr = float(config.get("confidence_threshold", 0.70))
        entities = [e for e in entities if float(getattr(e, "confidence", 1.0)) >= thr]

        # Optionally cap count
        max_entities = int(config.get("max_entities", 100_000))
        if len(entities) > max_entities:
            entities = entities[:max_entities]
        return entities

    # ---------- Gate A + selection ----------
    def _extract_column_entities(
        self,
        df: pd.DataFrame,
        column: ColumnProfile,
        config: Dict[str, Any],
    ) -> List[Entity]:
        """Collect candidates per column, then pick one best entity unless disabled."""
        entities: List[Entity] = []
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
        if top_regex and top_regex.entity_type in hard_exit_types and top_regex.confidence >= 0.90:
            return [top_regex]

        # Strategy 2: ID/sequential/uniqueness analysis
        if column.data_type in [DataType.INTEGER, DataType.STRING]:
            entities.extend(self._extract_id_entities(s, column, config))

        # Strategy 3 (LLM): only if nothing else found with confidence
        if config.get("use_llm", True) and not entities:
            try:
                entities.extend(self._extract_llm_entities(s, column, config))
            except Exception as e:
                logger.warning(f"LLM extraction failed for column {name}: {e}")

        # Strategy 4: pattern-based (percent/latlon/year/etc.)
        entities.extend(self._extract_pattern_entities(s, column, config))

        # Final choice: pick exactly one entity per column (default)
        if config.get("one_entity_per_column", True) and entities:
            return [self._choose_best_entity(entities, column, config)]
        return entities

    # ---------- Gate A: validators & regex ----------
    def _extract_regex_entities(
        self, s: pd.Series, column: ColumnProfile, config: Dict[str, Any]
    ) -> List[Entity]:
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

        out: List[Entity] = []
        checks: List[Tuple[str, re.Pattern]] = [
            ("email", _REG_EMAIL),
            ("url", _REG_URL),
            ("ip_address", _REG_IP),
            ("uuid", _REG_UUID),
            ("credit_card", _REG_CREDIT_CARD),
            ("phone", _REG_PHONE),
            ("postal_code", _REG_POSTAL_5),
        ]
        for t, rx in checks:
            r = ratio(rx)
            if r >= 0.70:  # strong validator
                out.append(
                    Entity(
                        name=column.name,
                        entity_type=t,
                        source_columns=[column.name],
                        confidence=float(r),
                        description=f"Validated as {t} by pattern checks",
                    )
                )
        return out

    # ---------- Gate A: ID/sequential/uniqueness ----------
    def _extract_id_entities(
        self, s: pd.Series, column: ColumnProfile, config: Dict[str, Any]
    ) -> List[Entity]:
        out: List[Entity] = []
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
        loose_uuid_hits = sum(1 for v in sample if _REG_HEXISH_UUID.match(str(v).strip()))
        loose_ratio = loose_uuid_hits / max(len(sample), 1)

        # Decision rules
        name_lower = column.name.lower()
        id_prior = ("id" in name_lower) or (name_lower.endswith("_id"))

        if ur >= 0.98 and (monotonic or id_prior):
            out.append(
                Entity(
                    name=column.name,
                    entity_type="sequential_id" if monotonic else "identifier",
                    source_columns=[column.name],
                    confidence=float(min(1.0, 0.7 + 0.3 * ur)),
                    description="High uniqueness; ID/name prior/sequence detected",
                )
            )
        elif ur >= 0.95 or loose_ratio >= 0.7:
            out.append(
                Entity(
                    name=column.name,
                    entity_type="identifier",
                    source_columns=[column.name],
                    confidence=float(max(0.70, min(0.95, ur))),
                    description="High uniqueness suggests identifier",
                )
            )
        return out

    # ---------- Gate A: other patterns (percent/latlon/year) ----------
    def _extract_pattern_entities(
        self, s: pd.Series, column: ColumnProfile, config: Dict[str, Any]
    ) -> List[Entity]:
        out: List[Entity] = []
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
                v = str(v).strip()
                if rx.match(v):
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
            out.append(
                Entity(
                    name=column.name,
                    entity_type="measurement",
                    source_columns=[column.name],
                    confidence=float(pr),
                    description="Percentage measurement (0–100%)",
                )
            )

        latr = latlon_ratio("lat")
        lonr = latlon_ratio("lon")
        if latr >= 0.80:
            out.append(
                Entity(
                    name=column.name,
                    entity_type="location_latitude",
                    source_columns=[column.name],
                    confidence=float(latr),
                    description="Latitude values",
                )
            )
        if lonr >= 0.80:
            out.append(
                Entity(
                    name=column.name,
                    entity_type="location_longitude",
                    source_columns=[column.name],
                    confidence=float(lonr),
                    description="Longitude values",
                )
            )

        yr = year_ratio()
        if yr >= 0.90 or any(k in column.name.lower() for k in ("year", "yr")):
            out.append(
                Entity(
                    name=column.name,
                    entity_type="time_dimension",
                    source_columns=[column.name],
                    confidence=float(max(0.7, yr)),
                    description="Year-like time dimension",
                )
            )
        return out

    # ---------- Gate C: LLM (last resort, deterministic & cached) ----------
    def _extract_llm_entities(
        self, s: pd.Series, column: ColumnProfile, config: Dict[str, Any]
    ) -> List[Entity]:
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

        entities: List[Entity] = []
        for r in (results or []):
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
                cache.write_text(json.dumps([e.__dict__ for e in entities], ensure_ascii=False))
            except Exception:
                pass
        return entities

    def _extract_business_entities_llm(
        self,
        df: pd.DataFrame,
        columns: List[ColumnProfile],
        config: Dict[str, Any],
    ) -> List[Entity]:
        if not self.llm_manager:
            return []
        # Small, deterministic context: schema + few representative rows
        sample_rows = df.head(int(config.get("llm_context_rows", 20))).to_dict(orient="records")
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
        entities: List[Entity] = []
        for r in (results or []):
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
                cache.write_text(json.dumps([e.__dict__ for e in entities], ensure_ascii=False))
            except Exception:
                pass
        return entities

    # ---------- selection: pick best entity per column ----------
    def _choose_best_entity(
        self, entities: List[Entity], column: ColumnProfile, config: Dict[str, Any]
    ) -> Entity:
        PRIORITY: List[str] = [
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
            if any(k in name for k in ("pct", "percent", "rate", "%")) and t == "measurement":
                score += 0.1
            if any(k in name for k in ("lat", "latitude")) and t.startswith("location_lat"):
                score += 0.1
            if any(k in name for k in ("lon", "lng", "longitude")) and t.startswith("location_lon"):
                score += 0.1
            if any(k in name for k in ("zip", "postal")) and t in ("postal_code", "address"):
                score += 0.1
            return score

        def pri_idx(e: Entity) -> int:
            try:
                return PRIORITY.index(e.entity_type)
            except ValueError:
                return len(PRIORITY)

        ranked = sorted(
            entities,
            key=lambda e: (-(float(getattr(e, "confidence", 0.0)) + name_prior(e)), pri_idx(e)),
        )
        return ranked[0]

    # ---------- consolidation: dedup by meaning ----------
    def _deduplicate_by_embeddings(self, entities: List[Entity], config: Dict[str, Any]) -> List[Entity]:
        if not entities:
            return entities
        thr = float(config.get("dedup_similarity_threshold", 0.90))
        if not self.embeddings:
            # basic textual dedup (exact same signature)
            seen = set()
            out: List[Entity] = []
            for e in entities:
                sig = (e.name, e.entity_type, tuple(sorted(e.source_columns)))
                if sig in seen:
                    continue
                seen.add(sig)
                out.append(e)
            return out

        # With embeddings: cluster by cosine sim >= thr
        vecs = self.embeddings.encode([self._entity_signature_text(e) for e in entities])
        used = [False] * len(entities)
        clusters: List[List[int]] = []
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
        merged: List[Entity] = []
        for idxs in clusters:
            cand = max((entities[k] for k in idxs), key=lambda e: float(getattr(e, "confidence", 0.0)))
            merged.append(cand)
        return merged

    @staticmethod
    def _entity_signature_text(e: Entity) -> str:
        return f"{e.name}|{e.entity_type}|{','.join(sorted(e.source_columns or []))}"

    # ---------- prompts ----------
    @staticmethod
    def _prompt_for_column(column: ColumnProfile, sample_values: List[str]) -> str:
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
    def _prompt_for_business_entities(context: Dict[str, Any]) -> str:
        return (
            "Identify any high-level business entities implied by the dataset schema.\n"
            "Return JSON list of objects: {name, entity_type, source_columns, confidence, reason}.\n"
            f"Context: {json.dumps(context, ensure_ascii=False)[:4000]}"
        )

    # ---------- IO & sampling ----------
    @staticmethod
    def _safe_read_csv(path: str | Path, usecols: Optional[List[str]] = None) -> pd.DataFrame:
        # You can swap this for DuckDB/Polars if desired. Keep deterministic.
        df = pd.read_csv(path, usecols=usecols, low_memory=False)
        return df

    @staticmethod
    def _det_sample_unique_sorted(s: pd.Series, config: Dict[str, Any]) -> List[str]:
        maxn = int(config.get("max_entities_per_column", 200))
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
