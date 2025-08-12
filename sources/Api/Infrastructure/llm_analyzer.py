"""
LLM Analyzer Infrastructure

Infrastructure component for using local LLM to analyze dataset connections.
"""

import json
import logging
import subprocess
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path

from ..Domain.models import LLMAnalysisResult, ConnectionType

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """Analyzer for using local LLM to detect dataset connections."""
    
    def __init__(self, model_path: Optional[str] = None, use_local_llm: bool = True):
        """
        Initialize the LLM analyzer.
        
        Args:
            model_path: Path to local LLM model (optional)
            use_local_llm: Whether to use local LLM or fallback to rule-based analysis
        """
        self.model_path = model_path
        self.use_local_llm = use_local_llm
        self.fallback_analyzer = FallbackAnalyzer()
        
        # Check if local LLM is available
        if self.use_local_llm and not self._check_local_llm_availability():
            logger.warning("Local LLM not available, falling back to rule-based analysis")
            self.use_local_llm = False
    
    def analyze_connection(self, context: Dict[str, Any]) -> LLMAnalysisResult:
        """
        Analyze a potential connection between two datasets.
        
        Args:
            context: Context containing information about the datasets and columns
            
        Returns:
            LLMAnalysisResult with analysis details
        """
        try:
            if self.use_local_llm:
                return self._analyze_with_local_llm(context)
            else:
                return self._analyze_with_fallback(context)
        except Exception as e:
            logger.error(f"Error in LLM analysis: {str(e)}")
            return self._analyze_with_fallback(context)
    
    def _analyze_with_local_llm(self, context: Dict[str, Any]) -> LLMAnalysisResult:
        """Analyze using local LLM."""
        try:
            # Prepare prompt for LLM
            prompt = self._create_analysis_prompt(context)
            
            # Call local LLM
            response = self._call_local_llm(prompt)
            
            # Parse LLM response
            return self._parse_llm_response(response, context)
            
        except Exception as e:
            logger.error(f"Error in local LLM analysis: {str(e)}")
            return self._analyze_with_fallback(context)
    
    def _analyze_with_fallback(self, context: Dict[str, Any]) -> LLMAnalysisResult:
        """Analyze using fallback rule-based approach."""
        return self.fallback_analyzer.analyze_connection(context)
    
    def _create_analysis_prompt(self, context: Dict[str, Any]) -> str:
        """Create a prompt for LLM analysis."""
        
        new_collection = context["new_collection"]
        existing_collection = context["existing_collection"]
        column_pair = context["column_pair"]
        
        prompt = f"""
You are a data scientist analyzing potential connections between two datasets. Please analyze the following information and provide a detailed assessment.

NEW DATASET: {new_collection['name']}
- Total rows: {new_collection['total_rows']}
- Columns: {', '.join(new_collection['columns'])}
- Column details: {json.dumps(new_collection['column_info'], indent=2)}

EXISTING DATASET: {existing_collection['name']}
- Total rows: {existing_collection['total_rows']}
- Columns: {', '.join(existing_collection['columns'])}
- Column details: {json.dumps(existing_collection['column_info'], indent=2)}

COLUMN PAIR TO ANALYZE:
- New dataset column: {column_pair['new_column']}
- Existing dataset column: {column_pair['existing_column']}

Please analyze this potential connection and provide:

1. REASONING: Detailed explanation of why these columns might be related
2. CONFIDENCE_SCORE: A score between 0.0 and 1.0 indicating confidence in the connection
3. CONNECTION_TYPE: One of: semantic_match, foreign_key, business_rule, temporal, spatial, hierarchical, transactional
4. BUSINESS_CONTEXT: Business context explanation
5. SUGGESTED_JOIN_STRATEGY: Recommended join strategy (inner_join, left_join, right_join, outer_join)
6. POTENTIAL_ISSUES: List of potential issues with this connection
7. RECOMMENDATIONS: List of recommendations for using this connection

Respond in JSON format:
{{
    "reasoning": "...",
    "confidence_score": 0.85,
    "connection_type": "foreign_key",
    "business_context": "...",
    "suggested_join_strategy": "inner_join",
    "potential_issues": ["..."],
    "recommendations": ["..."]
}}
"""
        return prompt
    
    def _call_local_llm(self, prompt: str) -> str:
        """Call local LLM with the given prompt."""
        try:
            # This is a placeholder for actual local LLM integration
            # You can integrate with models like:
            # - Ollama (ollama run llama2)
            # - LocalAI
            # - Custom model serving
            
            # For now, we'll simulate a local LLM call
            return self._simulate_local_llm_call(prompt)
            
        except Exception as e:
            logger.error(f"Error calling local LLM: {str(e)}")
            raise
    
    def _simulate_local_llm_call(self, prompt: str) -> str:
        """Simulate a local LLM call for development/testing."""
        # This is a mock response for development
        # In production, this would call an actual local LLM
        
        new_col = "customer_id"  # Extract from prompt
        existing_col = "customer_id"  # Extract from prompt
        
        if "customer_id" in prompt and "customer_id" in prompt:
            return json.dumps({
                "reasoning": f"The columns '{new_col}' and '{existing_col}' appear to be the same identifier field, likely representing customer IDs. This suggests a foreign key relationship where one dataset references customers from another dataset.",
                "confidence_score": 0.95,
                "connection_type": "foreign_key",
                "business_context": "This connection enables linking customer information across different business processes, such as orders, transactions, and customer profiles.",
                "suggested_join_strategy": "inner_join",
                "potential_issues": [
                    "Data type mismatches between the columns",
                    "Potential data quality issues in customer IDs",
                    "Need to verify referential integrity"
                ],
                "recommendations": [
                    "Verify data types match between columns",
                    "Check for null values in customer ID columns",
                    "Validate referential integrity before joining",
                    "Consider indexing on customer ID columns for performance"
                ]
            })
        elif "name" in prompt and "name" in prompt:
            return json.dumps({
                "reasoning": f"The columns '{new_col}' and '{existing_col}' both contain name information, suggesting a semantic relationship for entity matching.",
                "confidence_score": 0.75,
                "connection_type": "semantic_match",
                "business_context": "Name-based matching can be used for entity resolution and deduplication across datasets.",
                "suggested_join_strategy": "left_join",
                "potential_issues": [
                    "Name variations and typos",
                    "Different naming conventions",
                    "Potential for false matches"
                ],
                "recommendations": [
                    "Use fuzzy matching algorithms",
                    "Implement name normalization",
                    "Consider additional matching criteria",
                    "Validate matches manually for critical data"
                ]
            })
        else:
            return json.dumps({
                "reasoning": f"The columns '{new_col}' and '{existing_col}' may have some relationship, but the connection is not immediately clear.",
                "confidence_score": 0.45,
                "connection_type": "semantic_match",
                "business_context": "Further analysis needed to determine the business relationship between these columns.",
                "suggested_join_strategy": "left_join",
                "potential_issues": [
                    "Unclear business relationship",
                    "Low confidence in connection",
                    "Risk of incorrect joins"
                ],
                "recommendations": [
                    "Review business requirements",
                    "Analyze data patterns more deeply",
                    "Consider manual validation",
                    "Document the relationship if confirmed"
                ]
            })
    
    def _parse_llm_response(self, response: str, context: Dict[str, Any]) -> LLMAnalysisResult:
        """Parse LLM response into LLMAnalysisResult."""
        try:
            # Parse JSON response
            parsed = json.loads(response)
            
            # Map connection type
            connection_type_map = {
                "semantic_match": ConnectionType.SEMANTIC_MATCH,
                "foreign_key": ConnectionType.FOREIGN_KEY,
                "business_rule": ConnectionType.BUSINESS_RULE,
                "temporal": ConnectionType.TEMPORAL,
                "spatial": ConnectionType.SPATIAL,
                "hierarchical": ConnectionType.HIERARCHICAL,
                "transactional": ConnectionType.TRANSACTIONAL
            }
            
            connection_type = connection_type_map.get(
                parsed.get("connection_type", "semantic_match"),
                ConnectionType.SEMANTIC_MATCH
            )
            
            return LLMAnalysisResult(
                reasoning=parsed.get("reasoning", ""),
                confidence_score=float(parsed.get("confidence_score", 0.0)),
                connection_type=connection_type,
                business_context=parsed.get("business_context", ""),
                suggested_join_strategy=parsed.get("suggested_join_strategy", "inner_join"),
                potential_issues=parsed.get("potential_issues", []),
                recommendations=parsed.get("recommendations", [])
            )
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            return self._analyze_with_fallback(context)
    
    def _check_local_llm_availability(self) -> bool:
        """Check if local LLM is available."""
        try:
            # Check for common local LLM tools
            # You can customize this based on your setup
            
            # Check for Ollama
            result = subprocess.run(["ollama", "--version"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info("Ollama detected for local LLM")
                return True
            
            # Check for other local LLM tools
            # Add checks for LocalAI, custom models, etc.
            
            return False
            
        except Exception as e:
            logger.debug(f"Local LLM availability check failed: {str(e)}")
            return False


class FallbackAnalyzer:
    """Fallback rule-based analyzer when LLM is not available."""
    
    def analyze_connection(self, context: Dict[str, Any]) -> LLMAnalysisResult:
        """Analyze connection using rule-based approach."""
        
        new_collection = context["new_collection"]
        existing_collection = context["existing_collection"]
        column_pair = context["column_pair"]
        
        new_col = column_pair["new_column"]
        existing_col = column_pair["existing_column"]
        
        # Rule-based analysis
        confidence_score = self._calculate_confidence_score(new_col, existing_col)
        connection_type = self._determine_connection_type(new_col, existing_col)
        reasoning = self._generate_reasoning(new_col, existing_col, confidence_score)
        
        return LLMAnalysisResult(
            reasoning=reasoning,
            confidence_score=confidence_score,
            connection_type=connection_type,
            business_context=self._generate_business_context(new_col, existing_col),
            suggested_join_strategy=self._suggest_join_strategy(confidence_score),
            potential_issues=self._identify_potential_issues(new_col, existing_col),
            recommendations=self._generate_recommendations(confidence_score)
        )
    
    def _calculate_confidence_score(self, col1: str, col2: str) -> float:
        """Calculate confidence score based on column name similarity."""
        col1_lower = col1.lower()
        col2_lower = col2.lower()
        
        # Exact match
        if col1_lower == col2_lower:
            return 1.0
        
        # Contains match
        if col1_lower in col2_lower or col2_lower in col1_lower:
            return 0.8
        
        # ID pattern match
        if "id" in col1_lower and "id" in col2_lower:
            return 0.7
        
        # Name pattern match
        if "name" in col1_lower and "name" in col2_lower:
            return 0.6
        
        # Customer pattern match
        if "customer" in col1_lower and "customer" in col2_lower:
            return 0.9
        
        # Order pattern match
        if "order" in col1_lower and "order" in col2_lower:
            return 0.9
        
        # Product pattern match
        if "product" in col1_lower and "product" in col2_lower:
            return 0.8
        
        return 0.3
    
    def _determine_connection_type(self, col1: str, col2: str) -> ConnectionType:
        """Determine connection type based on column names."""
        col1_lower = col1.lower()
        col2_lower = col2.lower()
        
        if "id" in col1_lower and "id" in col2_lower:
            return ConnectionType.FOREIGN_KEY
        
        if "date" in col1_lower or "time" in col1_lower or "date" in col2_lower or "time" in col2_lower:
            return ConnectionType.TEMPORAL
        
        if "location" in col1_lower or "address" in col1_lower or "location" in col2_lower or "address" in col2_lower:
            return ConnectionType.SPATIAL
        
        return ConnectionType.SEMANTIC_MATCH
    
    def _generate_reasoning(self, col1: str, col2: str, confidence: float) -> str:
        """Generate reasoning for the connection."""
        if confidence >= 0.9:
            return f"The columns '{col1}' and '{col2}' are highly likely to represent the same entity or identifier, suggesting a strong relationship between the datasets."
        elif confidence >= 0.7:
            return f"The columns '{col1}' and '{col2}' show similar patterns and likely represent related concepts, indicating a potential relationship."
        elif confidence >= 0.5:
            return f"The columns '{col1}' and '{col2}' may have some relationship, but further analysis is recommended to confirm the connection."
        else:
            return f"The columns '{col1}' and '{col2}' show minimal similarity, suggesting a weak or no relationship between the datasets."
    
    def _generate_business_context(self, col1: str, col2: str) -> str:
        """Generate business context explanation."""
        return f"These columns may enable linking data across different business processes, allowing for comprehensive analysis and insights."
    
    def _suggest_join_strategy(self, confidence: float) -> str:
        """Suggest join strategy based on confidence."""
        if confidence >= 0.8:
            return "inner_join"
        elif confidence >= 0.6:
            return "left_join"
        else:
            return "outer_join"
    
    def _identify_potential_issues(self, col1: str, col2: str) -> list:
        """Identify potential issues with the connection."""
        issues = []
        
        if col1.lower() != col2.lower():
            issues.append("Column names are not identical")
        
        issues.append("Data types should be verified")
        issues.append("Data quality should be assessed")
        
        return issues
    
    def _generate_recommendations(self, confidence: float) -> list:
        """Generate recommendations based on confidence."""
        recommendations = ["Verify data types match between columns"]
        
        if confidence < 0.8:
            recommendations.append("Perform manual validation of the connection")
            recommendations.append("Consider additional matching criteria")
        
        recommendations.append("Document the relationship for future reference")
        
        return recommendations 