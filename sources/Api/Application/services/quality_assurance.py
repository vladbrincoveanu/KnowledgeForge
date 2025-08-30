"""Quality Assurance Module for extraction validation, monitoring, and quality metrics."""

import logging
import json
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
import pandas as pd
from pathlib import Path
import networkx as nx
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .metadata_store import AdvancedMetadataStore
from .embedding_manager import EmbeddingManager

logger = logging.getLogger(__name__)


@dataclass
class ValidationRule:
    """Quality validation rule definition."""
    rule_id: str
    rule_name: str
    rule_type: str  # 'naming', 'cardinality', 'cycle', 'property', 'statistical'
    severity: str  # 'error', 'warning', 'info'
    description: str
    enabled: bool = True
    threshold: Optional[float] = None
    parameters: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Result of a validation check."""
    rule_id: str
    rule_name: str
    validation_type: str
    passed: bool
    violations: List[Dict[str, Any]]
    severity: str
    confidence: float
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass
class QualityMetrics:
    """Comprehensive quality metrics."""
    precision_estimate: float
    recall_estimate: float
    f1_score: float
    confidence_calibration: float
    extraction_coverage: float
    inter_annotator_agreement: float
    overall_quality_score: float
    calculated_at: datetime
    sample_size: int


@dataclass
class AnomalyAlert:
    """Anomaly detection alert."""
    alert_id: str
    alert_type: str  # 'schema_change', 'performance_drop', 'pattern_anomaly'
    severity: str  # 'critical', 'high', 'medium', 'low'
    description: str
    detected_at: datetime
    affected_entities: List[str]
    affected_relationships: List[str]
    confidence: float
    recommended_actions: List[str]


class QualityAssurance:
    """Quality assurance system for extraction validation and monitoring."""
    
    def __init__(self, metadata_store: AdvancedMetadataStore,
                 embedding_manager: Optional[EmbeddingManager] = None,
                 alert_threshold: float = 0.8):
        """Initialize the quality assurance system.
        
        Args:
            metadata_store: Metadata store for data access
            embedding_manager: Optional embedding manager for similarity analysis
            alert_threshold: Threshold for anomaly alerts
        """
        self.metadata_store = metadata_store
        self.embedding_manager = embedding_manager
        self.alert_threshold = alert_threshold
        
        # Initialize validation rules
        self.validation_rules = self._initialize_validation_rules()
        
        # Performance tracking
        self.validation_history: List[ValidationResult] = []
        self.anomaly_alerts: List[AnomalyAlert] = []
        self.quality_trends: List[QualityMetrics] = []
        
        # Statistical baselines
        self.confidence_baseline: Optional[Dict[str, float]] = None
        self.extraction_patterns_baseline: Optional[Dict[str, Any]] = None
        
        logger.info("QualityAssurance system initialized successfully")
    
    def _initialize_validation_rules(self) -> List[ValidationRule]:
        """Initialize default validation rules."""
        rules = [
            # Naming convention rules
            ValidationRule(
                rule_id="entity_naming_convention",
                rule_name="Entity Naming Convention",
                rule_type="naming",
                severity="warning",
                description="Entities should follow naming conventions",
                parameters={
                    'min_length': 2,
                    'max_length': 100,
                    'allowed_chars': 'alphanumeric_spaces_hyphens_underscores'
                }
            ),
            
            # Cardinality constraints
            ValidationRule(
                rule_id="relationship_cardinality",
                rule_name="Relationship Cardinality",
                rule_type="cardinality",
                severity="error",
                description="Relationships should respect cardinality constraints",
                parameters={
                    'max_relationships_per_entity': 50,
                    'max_self_relationships': 0
                }
            ),
            
            # Cycle detection
            ValidationRule(
                rule_id="relationship_cycles",
                rule_name="Relationship Cycles",
                rule_type="cycle",
                severity="error",
                description="Relationships should not create cycles",
                parameters={
                    'max_cycle_length': 3,
                    'allowed_cycle_types': ['hierarchical']
                }
            ),
            
            # Required properties
            ValidationRule(
                rule_id="required_properties",
                rule_name="Required Properties",
                rule_type="property",
                severity="error",
                description="Required properties must be present",
                parameters={
                    'entity_required': ['name', 'entity_type'],
                    'relationship_required': ['type', 'source_entity_id', 'target_entity_id']
                }
            ),
            
            # Statistical validation
            ValidationRule(
                rule_id="confidence_outliers",
                rule_name="Confidence Score Outliers",
                rule_type="statistical",
                severity="warning",
                description="Detect outliers in confidence scores",
                threshold=2.0,  # Standard deviations
                parameters={
                    'method': 'zscore',
                    'min_samples': 10
                }
            )
        ]
        
        return rules
    
    def validate_extraction_quality(self, entities: List[Dict[str, Any]],
                                  relationships: List[Dict[str, Any]]) -> List[ValidationResult]:
        """Perform comprehensive quality validation on extractions.
        
        Args:
            entities: List of extracted entities
            relationships: List of extracted relationships
            
        Returns:
            List of validation results
        """
        validation_results = []
        
        try:
            # Rule-based validation
            for rule in self.validation_rules:
                if not rule.enabled:
                    continue
                
                if rule.rule_type == "naming":
                    result = self._validate_naming_conventions(entities, rule)
                elif rule.rule_type == "cardinality":
                    result = self._validate_cardinality_constraints(entities, relationships, rule)
                elif rule.rule_type == "cycle":
                    result = self._validate_relationship_cycles(relationships, rule)
                elif rule.rule_type == "property":
                    result = self._validate_required_properties(entities, relationships, rule)
                elif rule.rule_type == "statistical":
                    result = self._validate_statistical_patterns(entities, relationships, rule)
                else:
                    continue
                
                validation_results.append(result)
                self.validation_history.append(result)
            
            # Statistical validation
            statistical_results = self._perform_statistical_validation(entities, relationships)
            validation_results.extend(statistical_results)
            
            logger.info(f"Quality validation completed: {len(validation_results)} rules checked")
            return validation_results
            
        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            return []
    
    def _validate_naming_conventions(self, entities: List[Dict[str, Any]], 
                                   rule: ValidationRule) -> ValidationResult:
        """Validate entity naming conventions."""
        violations = []
        passed = True
        
        try:
            params = rule.parameters or {}
            min_length = params.get('min_length', 2)
            max_length = params.get('max_length', 100)
            
            for entity in entities:
                name = entity.get('name', '')
                
                # Check length constraints
                if len(name) < min_length:
                    violations.append({
                        'entity_id': entity.get('id', ''),
                        'issue': f"Name too short: {len(name)} < {min_length}",
                        'value': name
                    })
                    passed = False
                
                if len(name) > max_length:
                    violations.append({
                        'entity_id': entity.get('id', ''),
                        'issue': f"Name too long: {len(name)} > {max_length}",
                        'value': name
                    })
                    passed = False
                
                # Check for invalid characters
                if not name.replace(' ', '').replace('-', '').replace('_', '').isalnum():
                    violations.append({
                        'entity_id': entity.get('id', ''),
                        'issue': "Contains invalid characters",
                        'value': name
                    })
                    passed = False
            
            return ValidationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                validation_type=rule.rule_type,
                passed=passed,
                violations=violations,
                severity=rule.severity,
                confidence=1.0 - (len(violations) / max(len(entities), 1)),
                timestamp=datetime.now(),
                metadata={'total_entities': len(entities), 'violation_count': len(violations)}
            )
            
        except Exception as e:
            logger.error(f"Naming convention validation failed: {e}")
            return ValidationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                validation_type=rule.rule_type,
                passed=False,
                violations=[],
                severity=rule.severity,
                confidence=0.0,
                timestamp=datetime.now(),
                metadata={'error': str(e)}
            )
    
    def _validate_cardinality_constraints(self, entities: List[Dict[str, Any]],
                                        relationships: List[Dict[str, Any]],
                                        rule: ValidationRule) -> ValidationResult:
        """Validate relationship cardinality constraints."""
        violations = []
        passed = True
        
        try:
            params = rule.parameters or {}
            max_relationships = params.get('max_relationships_per_entity', 50)
            max_self_relationships = params.get('max_self_relationships', 0)
            
            # Count relationships per entity
            entity_relationship_counts = {}
            self_relationships = []
            
            for rel in relationships:
                source_id = rel.get('source_entity_id', '')
                target_id = rel.get('target_entity_id', '')
                
                # Count outgoing relationships
                if source_id not in entity_relationship_counts:
                    entity_relationship_counts[source_id] = 0
                entity_relationship_counts[source_id] += 1
                
                # Check for self-relationships
                if source_id == target_id:
                    self_relationships.append(rel)
            
            # Check cardinality violations
            for entity_id, count in entity_relationship_counts.items():
                if count > max_relationships:
                    violations.append({
                        'entity_id': entity_id,
                        'issue': f"Too many relationships: {count} > {max_relationships}",
                        'value': count
                    })
                    passed = False
            
            # Check self-relationship violations
            if len(self_relationships) > max_self_relationships:
                violations.append({
                    'entity_id': 'multiple',
                    'issue': f"Too many self-relationships: {len(self_relationships)} > {max_self_relationships}",
                    'value': len(self_relationships)
                })
                passed = False
            
            return ValidationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                validation_type=rule.rule_type,
                passed=passed,
                violations=violations,
                severity=rule.severity,
                confidence=1.0 - (len(violations) / max(len(relationships), 1)),
                timestamp=datetime.now(),
                metadata={'total_relationships': len(relationships), 'violation_count': len(violations)}
            )
            
        except Exception as e:
            logger.error(f"Cardinality validation failed: {e}")
            return ValidationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                validation_type=rule.rule_type,
                passed=False,
                violations=[],
                severity=rule.severity,
                confidence=0.0,
                timestamp=datetime.now(),
                metadata={'error': str(e)}
            )
    
    def _validate_relationship_cycles(self, relationships: List[Dict[str, Any]],
                                    rule: ValidationRule) -> ValidationResult:
        """Validate relationship cycles."""
        violations = []
        passed = True
        
        try:
            params = rule.parameters or {}
            max_cycle_length = params.get('max_cycle_length', 3)
            
            # Build graph for cycle detection
            G = nx.DiGraph()
            
            for rel in relationships:
                source_id = rel.get('source_entity_id', '')
                target_id = rel.get('target_entity_id', '')
                if source_id and target_id:
                    G.add_edge(source_id, target_id)
            
            # Detect cycles
            try:
                cycles = list(nx.simple_cycles(G))
                long_cycles = [cycle for cycle in cycles if len(cycle) > max_cycle_length]
                
                for cycle in long_cycles:
                    violations.append({
                        'cycle': cycle,
                        'issue': f"Cycle too long: {len(cycle)} > {max_cycle_length}",
                        'value': len(cycle)
                    })
                    passed = False
                    
            except nx.NetworkXNoCycle:
                # No cycles found
                pass
            
            return ValidationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                validation_type=rule.rule_type,
                passed=passed,
                violations=violations,
                severity=rule.severity,
                confidence=1.0 - (len(violations) / max(len(relationships), 1)),
                timestamp=datetime.now(),
                metadata={'total_relationships': len(relationships), 'cycles_found': len(cycles) if 'cycles' in locals() else 0}
            )
            
        except Exception as e:
            logger.error(f"Cycle validation failed: {e}")
            return ValidationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                validation_type=rule.rule_type,
                passed=False,
                violations=[],
                severity=rule.severity,
                confidence=0.0,
                timestamp=datetime.now(),
                metadata={'error': str(e)}
            )
    
    def _validate_required_properties(self, entities: List[Dict[str, Any]],
                                    relationships: List[Dict[str, Any]],
                                    rule: ValidationRule) -> ValidationResult:
        """Validate required properties presence."""
        violations = []
        passed = True
        
        try:
            params = rule.parameters or {}
            entity_required = params.get('entity_required', ['name', 'entity_type'])
            relationship_required = params.get('relationship_required', ['type', 'source_entity_id', 'target_entity_id'])
            
            # Check entity properties
            for entity in entities:
                for prop in entity_required:
                    if prop not in entity or entity[prop] is None or entity[prop] == '':
                        violations.append({
                            'entity_id': entity.get('id', ''),
                            'issue': f"Missing required property: {prop}",
                            'value': 'missing'
                        })
                        passed = False
            
            # Check relationship properties
            for rel in relationships:
                for prop in relationship_required:
                    if prop not in rel or rel[prop] is None or rel[prop] == '':
                        violations.append({
                            'relationship_id': rel.get('id', ''),
                            'issue': f"Missing required property: {prop}",
                            'value': 'missing'
                        })
                        passed = False
            
            total_items = len(entities) + len(relationships)
            return ValidationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                validation_type=rule.rule_type,
                passed=passed,
                violations=violations,
                severity=rule.severity,
                confidence=1.0 - (len(violations) / max(total_items, 1)),
                timestamp=datetime.now(),
                metadata={'total_items': total_items, 'violation_count': len(violations)}
            )
            
        except Exception as e:
            logger.error(f"Property validation failed: {e}")
            return ValidationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                validation_type=rule.rule_type,
                passed=False,
                violations=[],
                severity=rule.severity,
                confidence=0.0,
                timestamp=datetime.now(),
                metadata={'error': str(e)}
            )
    
    def _validate_statistical_patterns(self, entities: List[Dict[str, Any]],
                                     relationships: List[Dict[str, Any]],
                                     rule: ValidationRule) -> ValidationResult:
        """Validate statistical patterns."""
        violations = []
        passed = True
        
        try:
            if rule.rule_id == "confidence_outliers":
                # Detect confidence score outliers
                all_confidences = []
                
                for entity in entities:
                    conf = entity.get('confidence', 0.0)
                    if conf is not None:
                        all_confidences.append(conf)
                
                for rel in relationships:
                    conf = rel.get('confidence', 0.0)
                    if conf is not None:
                        all_confidences.append(conf)
                
                if len(all_confidences) >= 10:  # Minimum samples required
                    confidences = np.array(all_confidences)
                    z_scores = np.abs(stats.zscore(confidences))
                    threshold = rule.threshold or 2.0
                    
                    outlier_indices = np.where(z_scores > threshold)[0]
                    
                    for idx in outlier_indices:
                        violations.append({
                            'index': int(idx),
                            'issue': f"Confidence outlier: z-score {z_scores[idx]:.2f} > {threshold}",
                            'value': confidences[idx]
                        })
                        passed = False
            
            return ValidationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                validation_type=rule.rule_type,
                passed=passed,
                violations=violations,
                severity=rule.severity,
                confidence=1.0 - (len(violations) / max(len(all_confidences) if 'all_confidences' in locals() else 1, 1)),
                timestamp=datetime.now(),
                metadata={'total_samples': len(all_confidences) if 'all_confidences' in locals() else 0, 'outlier_count': len(violations)}
            )
            
        except Exception as e:
            logger.error(f"Statistical validation failed: {e}")
            return ValidationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                validation_type=rule.rule_type,
                passed=False,
                violations=[],
                severity=rule.severity,
                confidence=0.0,
                timestamp=datetime.now(),
                metadata={'error': str(e)}
            )
    
    def _perform_statistical_validation(self, entities: List[Dict[str, Any]],
                                      relationships: List[Dict[str, Any]]) -> List[ValidationResult]:
        """Perform additional statistical validation."""
        results = []
        
        try:
            # Confidence distribution analysis
            entity_confidences = [e.get('confidence', 0.0) for e in entities if e.get('confidence') is not None]
            rel_confidences = [r.get('confidence', 0.0) for r in relationships if r.get('confidence') is not None]
            
            if entity_confidences:
                # Check for unusual confidence distributions
                entity_conf_array = np.array(entity_confidences)
                mean_conf = np.mean(entity_conf_array)
                std_conf = np.std(entity_conf_array)
                
                if std_conf < 0.1:  # Very low variance
                    results.append(ValidationResult(
                        rule_id="confidence_variance",
                        rule_name="Confidence Variance Check",
                        validation_type="statistical",
                        passed=False,
                        violations=[{
                            'issue': f"Very low confidence variance: {std_conf:.3f}",
                            'value': std_conf
                        }],
                        severity="warning",
                        confidence=0.8,
                        timestamp=datetime.now(),
                        metadata={'mean_confidence': mean_conf, 'std_confidence': std_conf}
                    ))
            
            # Temporal consistency check (if timestamps available)
            if entities and 'created_at' in entities[0]:
                temporal_result = self._check_temporal_consistency(entities, relationships)
                if temporal_result:
                    results.append(temporal_result)
            
        except Exception as e:
            logger.error(f"Statistical validation failed: {e}")
        
        return results
    
    def _check_temporal_consistency(self, entities: List[Dict[str, Any]],
                                  relationships: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check temporal consistency of extractions."""
        try:
            # This would analyze timestamps for consistency patterns
            # For now, return None as placeholder
            return None
        except Exception:
            return None
    
    def detect_anomalies(self, entities: List[Dict[str, Any]],
                        relationships: List[Dict[str, Any]]) -> List[AnomalyAlert]:
        """Detect anomalies in extraction patterns and performance."""
        anomalies = []
        
        try:
            # Schema change detection
            schema_anomalies = self._detect_schema_changes(entities, relationships)
            anomalies.extend(schema_anomalies)
            
            # Performance drop detection
            performance_anomalies = self._detect_performance_drops(entities, relationships)
            anomalies.extend(performance_anomalies)
            
            # Pattern anomalies
            pattern_anomalies = self._detect_pattern_anomalies(entities, relationships)
            anomalies.extend(pattern_anomalies)
            
            # Store anomalies
            self.anomaly_alerts.extend(anomalies)
            
            logger.info(f"Anomaly detection completed: {len(anomalies)} anomalies found")
            return anomalies
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return []
    
    def _detect_schema_changes(self, entities: List[Dict[str, Any]],
                              relationships: List[Dict[str, Any]]) -> List[AnomalyAlert]:
        """Detect sudden schema changes."""
        anomalies = []
        
        try:
            # Analyze entity type distribution
            entity_types = {}
            for entity in entities:
                entity_type = entity.get('entity_type', 'UNKNOWN')
                entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
            
            # Check for unusual entity type patterns
            total_entities = len(entities)
            for entity_type, count in entity_types.items():
                proportion = count / total_entities
                
                # Alert if a single type dominates (>80%)
                if proportion > 0.8:
                    anomalies.append(AnomalyAlert(
                        alert_id=f"schema_{int(time.time())}",
                        alert_type="schema_change",
                        severity="medium",
                        description=f"Entity type {entity_type} dominates extraction ({proportion:.1%})",
                        detected_at=datetime.now(),
                        affected_entities=[e['id'] for e in entities if e.get('entity_type') == entity_type],
                        affected_relationships=[],
                        confidence=0.9,
                        recommended_actions=[
                            "Review entity type classification rules",
                            "Check for systematic extraction errors",
                            "Validate entity type distribution"
                        ]
                    ))
            
        except Exception as e:
            logger.error(f"Schema change detection failed: {e}")
        
        return anomalies
    
    def _detect_performance_drops(self, entities: List[Dict[str, Any]],
                                relationships: List[Dict[str, Any]]) -> List[AnomalyAlert]:
        """Detect extraction performance drops."""
        anomalies = []
        
        try:
            # Analyze confidence scores
            entity_confidences = [e.get('confidence', 0.0) for e in entities if e.get('confidence') is not None]
            rel_confidences = [r.get('confidence', 0.0) for r in relationships if r.get('confidence') is not None]
            
            if entity_confidences:
                avg_confidence = np.mean(entity_confidences)
                
                # Alert if average confidence is too low
                if avg_confidence < 0.6:
                    anomalies.append(AnomalyAlert(
                        alert_id=f"performance_{int(time.time())}",
                        alert_type="performance_drop",
                        severity="high",
                        description=f"Low average entity confidence: {avg_confidence:.3f}",
                        detected_at=datetime.now(),
                        affected_entities=[e['id'] for e in entities if e.get('confidence', 0.0) < 0.6],
                        affected_relationships=[],
                        confidence=0.8,
                        recommended_actions=[
                            "Review extraction model performance",
                            "Check for data quality issues",
                            "Consider model retraining"
                        ]
                    ))
            
        except Exception as e:
            logger.error(f"Performance drop detection failed: {e}")
        
        return anomalies
    
    def _detect_pattern_anomalies(self, entities: List[Dict[str, Any]],
                                relationships: List[Dict[str, Any]]) -> List[AnomalyAlert]:
        """Detect unusual entity/relationship patterns."""
        anomalies = []
        
        try:
            # Check for unusual relationship patterns
            if relationships:
                # Detect isolated entities (no relationships)
                entity_ids = {e['id'] for e in entities}
                rel_entity_ids = set()
                
                for rel in relationships:
                    rel_entity_ids.add(rel.get('source_entity_id', ''))
                    rel_entity_ids.add(rel.get('target_entity_id', ''))
                
                isolated_entities = entity_ids - rel_entity_ids
                
                if len(isolated_entities) > len(entity_ids) * 0.5:  # >50% isolated
                    anomalies.append(AnomalyAlert(
                        alert_id=f"pattern_{int(time.time())}",
                        alert_type="pattern_anomaly",
                        severity="medium",
                        description=f"High proportion of isolated entities: {len(isolated_entities)}/{len(entity_ids)}",
                        detected_at=datetime.now(),
                        affected_entities=list(isolated_entities),
                        affected_relationships=[],
                        confidence=0.7,
                        recommended_actions=[
                            "Review relationship discovery logic",
                            "Check for missing relationship patterns",
                            "Validate entity connectivity"
                        ]
                    ))
            
        except Exception as e:
            logger.error(f"Pattern anomaly detection failed: {e}")
        
        return anomalies
    
    def calculate_quality_metrics(self, entities: List[Dict[str, Any]],
                                relationships: List[Dict[str, Any]]) -> QualityMetrics:
        """Calculate comprehensive quality metrics."""
        try:
            # Precision/Recall estimation (using confidence as proxy)
            entity_confidences = [e.get('confidence', 0.0) for e in entities if e.get('confidence') is not None]
            rel_confidences = [r.get('confidence', 0.0) for r in relationships if r.get('confidence') is not None]
            
            all_confidences = entity_confidences + rel_confidences
            
            if all_confidences:
                # Use average confidence as precision estimate
                precision_estimate = np.mean(all_confidences)
                
                # Estimate recall based on coverage
                recall_estimate = min(1.0, len(entities) / max(1, len(entities) + len(relationships) * 0.1))
                
                # Calculate F1 score
                f1_score = 2 * (precision_estimate * recall_estimate) / (precision_estimate + recall_estimate) if (precision_estimate + recall_estimate) > 0 else 0
                
                # Confidence calibration (how well confidence reflects actual quality)
                confidence_calibration = self._calculate_confidence_calibration(all_confidences)
                
                # Extraction coverage
                extraction_coverage = len(entities) / max(1, len(entities) + len(relationships))
                
                # Inter-annotator agreement simulation
                inter_annotator_agreement = self._simulate_inter_annotator_agreement(entities, relationships)
                
                # Overall quality score
                overall_quality_score = np.mean([
                    precision_estimate,
                    recall_estimate,
                    confidence_calibration,
                    extraction_coverage,
                    inter_annotator_agreement
                ])
                
                metrics = QualityMetrics(
                    precision_estimate=precision_estimate,
                    recall_estimate=recall_estimate,
                    f1_score=f1_score,
                    confidence_calibration=confidence_calibration,
                    extraction_coverage=extraction_coverage,
                    inter_annotator_agreement=inter_annotator_agreement,
                    overall_quality_score=overall_quality_score,
                    calculated_at=datetime.now(),
                    sample_size=len(entities) + len(relationships)
                )
                
                self.quality_trends.append(metrics)
                logger.info(f"Quality metrics calculated: overall score {overall_quality_score:.3f}")
                return metrics
            
        except Exception as e:
            logger.error(f"Quality metrics calculation failed: {e}")
        
        # Return default metrics if calculation fails
        return QualityMetrics(
            precision_estimate=0.0,
            recall_estimate=0.0,
            f1_score=0.0,
            confidence_calibration=0.0,
            extraction_coverage=0.0,
            inter_annotator_agreement=0.0,
            overall_quality_score=0.0,
            calculated_at=datetime.now(),
            sample_size=0
        )
    
    def _calculate_confidence_calibration(self, confidences: List[float]) -> float:
        """Calculate confidence calibration score."""
        try:
            if len(confidences) < 10:
                return 0.5
            
            # Simple calibration: check if confidence distribution is reasonable
            conf_array = np.array(confidences)
            
            # Good calibration: confidence should be somewhat uniform
            # Bad calibration: all high or all low confidence
            std_conf = np.std(conf_array)
            mean_conf = np.mean(conf_array)
            
            # Penalize very low variance or extreme means
            if std_conf < 0.1 or mean_conf > 0.9 or mean_conf < 0.1:
                return 0.3
            elif std_conf < 0.2 or mean_conf > 0.8 or mean_conf < 0.2:
                return 0.6
            else:
                return 0.8
                
        except Exception:
            return 0.5
    
    def _simulate_inter_annotator_agreement(self, entities: List[Dict[str, Any]],
                                          relationships: List[Dict[str, Any]]) -> float:
        """Simulate inter-annotator agreement score."""
        try:
            # Simulate agreement based on consistency of extractions
            total_items = len(entities) + len(relationships)
            if total_items < 2:
                return 0.5
            
            # Check for consistency in entity types and relationship types
            entity_types = [e.get('entity_type', '') for e in entities]
            rel_types = [r.get('relationship_type', '') for r in relationships]
            
            # Calculate type diversity (more diversity suggests better agreement)
            entity_type_diversity = len(set(entity_types)) / max(len(entity_types), 1)
            rel_type_diversity = len(set(rel_types)) / max(len(rel_types), 1)
            
            # Simulate agreement score
            agreement_score = (entity_type_diversity + rel_type_diversity) / 2
            
            return min(1.0, agreement_score * 1.5)  # Scale to reasonable range
            
        except Exception:
            return 0.5
    
    def generate_quality_report(self, entities: List[Dict[str, Any]],
                              relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive quality report."""
        try:
            # Run all validations
            validation_results = self.validate_extraction_quality(entities, relationships)
            
            # Detect anomalies
            anomalies = self.detect_anomalies(entities, relationships)
            
            # Calculate quality metrics
            quality_metrics = self.calculate_quality_metrics(entities, relationships)
            
            # Generate report
            report = {
                'generated_at': datetime.now().isoformat(),
                'summary': {
                    'total_entities': len(entities),
                    'total_relationships': len(relationships),
                    'overall_quality_score': quality_metrics.overall_quality_score,
                    'validation_passed': sum(1 for r in validation_results if r.passed),
                    'validation_total': len(validation_results),
                    'anomalies_detected': len(anomalies)
                },
                'validation_results': [
                    {
                        'rule_id': r.rule_id,
                        'rule_name': r.rule_name,
                        'passed': r.passed,
                        'violations': len(r.violations),
                        'severity': r.severity,
                        'confidence': r.confidence
                    }
                    for r in validation_results
                ],
                'quality_metrics': {
                    'precision_estimate': quality_metrics.precision_estimate,
                    'recall_estimate': quality_metrics.recall_estimate,
                    'f1_score': quality_metrics.f1_score,
                    'confidence_calibration': quality_metrics.confidence_calibration,
                    'extraction_coverage': quality_metrics.extraction_coverage,
                    'inter_annotator_agreement': quality_metrics.inter_annotator_agreement
                },
                'anomalies': [
                    {
                        'type': a.alert_type,
                        'severity': a.severity,
                        'description': a.description,
                        'confidence': a.confidence,
                        'recommended_actions': a.recommended_actions
                    }
                    for a in anomalies
                ],
                'recommendations': self._generate_recommendations(validation_results, anomalies, quality_metrics)
            }
            
            logger.info("Quality report generated successfully")
            return report
            
        except Exception as e:
            logger.error(f"Quality report generation failed: {e}")
            return {'error': str(e)}
    
    def _generate_recommendations(self, validation_results: List[ValidationResult],
                                anomalies: List[AnomalyAlert],
                                quality_metrics: QualityMetrics) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Based on validation results
        failed_validations = [r for r in validation_results if not r.passed]
        if failed_validations:
            recommendations.append(f"Address {len(failed_validations)} failed validation rules")
        
        # Based on quality metrics
        if quality_metrics.overall_quality_score < 0.7:
            recommendations.append("Overall quality score is low - consider model retraining")
        
        if quality_metrics.confidence_calibration < 0.6:
            recommendations.append("Confidence calibration is poor - review confidence scoring")
        
        # Based on anomalies
        critical_anomalies = [a for a in anomalies if a.severity == 'critical']
        if critical_anomalies:
            recommendations.append(f"Address {len(critical_anomalies)} critical anomalies immediately")
        
        if not recommendations:
            recommendations.append("Quality is good - continue monitoring")
        
        return recommendations
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the quality assurance system."""
        return {
            'validation_history_count': len(self.validation_history),
            'anomaly_alerts_count': len(self.anomaly_alerts),
            'quality_trends_count': len(self.quality_trends),
            'active_rules_count': sum(1 for r in self.validation_rules if r.enabled),
            'alert_threshold': self.alert_threshold
        }
