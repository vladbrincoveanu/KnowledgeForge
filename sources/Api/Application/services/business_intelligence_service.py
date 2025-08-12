"""
Business Intelligence Service

Service for generating comprehensive business intelligence using enhanced LLM analysis.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from ...Domain.models import (
    BusinessIntelligenceRequest, BusinessIntelligenceResponse,
    BusinessOntology, DataSourceSuggestion, BusinessActionRecommendation,
    ComplexRelationshipExplanation, EnhancedLLMAnalysisResult
)
from ...Infrastructure.enhanced_llm_analyzer import EnhancedLLMAnalyzer
from ...Infrastructure.mongodb_connector import MongoDBConnector

logger = logging.getLogger(__name__)


class BusinessIntelligenceService:
    """Service for generating comprehensive business intelligence."""
    
    def __init__(self, mongodb_connector: MongoDBConnector, enhanced_llm_analyzer: EnhancedLLMAnalyzer):
        self.mongodb_connector = mongodb_connector
        self.enhanced_llm_analyzer = enhanced_llm_analyzer
    
    def generate_business_intelligence(self, request: BusinessIntelligenceRequest) -> BusinessIntelligenceResponse:
        """
        Generate comprehensive business intelligence from collections.
        
        Args:
            request: Business intelligence request
            
        Returns:
            BusinessIntelligenceResponse with comprehensive analysis
        """
        try:
            logger.info(f"Generating business intelligence for collections: {request.collection_names}")
            
            # Use enhanced LLM analyzer to generate business intelligence
            response = self.enhanced_llm_analyzer.generate_business_intelligence(request)
            
            if response.success:
                # Store generated business intelligence in MongoDB
                self._store_business_intelligence(response)
                
                # Generate additional insights based on existing edges
                self._enhance_with_existing_relationships(response, request.collection_names)
                
                logger.info(f"Successfully generated business intelligence for {len(request.collection_names)} collections")
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating business intelligence: {str(e)}")
            return BusinessIntelligenceResponse(
                success=False,
                message="Failed to generate business intelligence",
                error=str(e)
            )
    
    def get_business_ontologies(self, domain: Optional[str] = None) -> List[BusinessOntology]:
        """
        Get stored business ontologies, optionally filtered by domain.
        
        Args:
            domain: Optional domain to filter by
            
        Returns:
            List of business ontologies
        """
        try:
            return self._get_ontologies_from_db(domain)
        except Exception as e:
            logger.error(f"Error getting business ontologies: {str(e)}")
            return []
    
    def get_data_source_suggestions(self, collection_name: Optional[str] = None) -> List[DataSourceSuggestion]:
        """
        Get stored data source suggestions, optionally filtered by collection.
        
        Args:
            collection_name: Optional collection name to filter by
            
        Returns:
            List of data source suggestions
        """
        try:
            return self._get_suggestions_from_db(collection_name)
        except Exception as e:
            logger.error(f"Error getting data source suggestions: {str(e)}")
            return []
    
    def get_business_actions(self, action_type: Optional[str] = None) -> List[BusinessActionRecommendation]:
        """
        Get stored business actions, optionally filtered by type.
        
        Args:
            action_type: Optional action type to filter by
            
        Returns:
            List of business actions
        """
        try:
            return self._get_actions_from_db(action_type)
        except Exception as e:
            logger.error(f"Error getting business actions: {str(e)}")
            return []
    
    def get_relationship_explanations(self, collection_name: Optional[str] = None) -> List[ComplexRelationshipExplanation]:
        """
        Get stored relationship explanations, optionally filtered by collection.
        
        Args:
            collection_name: Optional collection name to filter by
            
        Returns:
            List of relationship explanations
        """
        try:
            return self._get_explanations_from_db(collection_name)
        except Exception as e:
            logger.error(f"Error getting relationship explanations: {str(e)}")
            return []
    
    def update_business_ontology(self, ontology_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a business ontology with new information.
        
        Args:
            ontology_id: ID of the ontology to update
            updates: Dictionary of updates to apply
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            updates['updated_at'] = datetime.utcnow()
            result = self.mongodb_connector.db.business_ontologies.update_one(
                {"id": ontology_id},
                {"$set": updates}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating business ontology {ontology_id}: {str(e)}")
            return False
    
    def mark_data_source_implemented(self, suggestion_id: str, implementation_notes: str = "") -> bool:
        """
        Mark a data source suggestion as implemented.
        
        Args:
            suggestion_id: ID of the suggestion to mark
            implementation_notes: Notes about the implementation
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            updates = {
                "status": "implemented",
                "implementation_notes": implementation_notes,
                "implemented_at": datetime.utcnow()
            }
            result = self.mongodb_connector.db.data_source_suggestions.update_one(
                {"id": suggestion_id},
                {"$set": updates}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error marking data source suggestion {suggestion_id} as implemented: {str(e)}")
            return False
    
    def mark_business_action_completed(self, action_id: str, completion_notes: str = "") -> bool:
        """
        Mark a business action as completed.
        
        Args:
            action_id: ID of the action to mark
            completion_notes: Notes about the completion
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            updates = {
                "status": "completed",
                "completion_notes": completion_notes,
                "completed_at": datetime.utcnow()
            }
            result = self.mongodb_connector.db.business_actions.update_one(
                {"id": action_id},
                {"$set": updates}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error marking business action {action_id} as completed: {str(e)}")
            return False
    
    def _store_business_intelligence(self, response: BusinessIntelligenceResponse):
        """Store generated business intelligence in MongoDB."""
        try:
            # Store ontologies
            for ontology in response.ontologies:
                self._store_ontology(ontology)
            
            # Store data source suggestions
            for suggestion in response.data_source_suggestions:
                self._store_suggestion(suggestion)
            
            # Store business actions
            for action in response.business_actions:
                self._store_action(action)
            
            # Store relationship explanations
            for explanation in response.relationship_explanations:
                self._store_explanation(explanation)
                
        except Exception as e:
            logger.error(f"Error storing business intelligence: {str(e)}")
    
    def _enhance_with_existing_relationships(self, response: BusinessIntelligenceResponse, collection_names: List[str]):
        """Enhance business intelligence with insights from existing relationships."""
        try:
            # Get existing edges for the collections
            edges = self._get_edges_for_collections(collection_names)
            
            if edges:
                # Add relationship-based insights
                for edge in edges:
                    # Enhance ontologies with relationship information
                    self._enhance_ontology_with_edge(response.ontologies, edge)
                    
                    # Add relationship-based data source suggestions
                    self._add_relationship_based_suggestions(response.data_source_suggestions, edge)
                    
                    # Add relationship-based business actions
                    self._add_relationship_based_actions(response.business_actions, edge)
                    
        except Exception as e:
            logger.error(f"Error enhancing with existing relationships: {str(e)}")
    
    def _enhance_ontology_with_edge(self, ontologies: List[BusinessOntology], edge):
        """Enhance ontologies with information from edges."""
        try:
            for ontology in ontologies:
                if edge.source_collection in ontology.source_collections or edge.target_collection in ontology.source_collections:
                    # Add edge information to ontology
                    if edge.connection_type.value not in ontology.relationships:
                        ontology.relationships.append(edge.connection_type.value)
                    
                    # Add business rules based on connection type
                    if edge.connection_type.value == "foreign_key":
                        rule = f"Referential integrity must be maintained between {edge.source_collection} and {edge.target_collection}"
                        if rule not in ontology.business_rules:
                            ontology.business_rules.append(rule)
                    
        except Exception as e:
            logger.error(f"Error enhancing ontology with edge: {str(e)}")
    
    def _add_relationship_based_suggestions(self, suggestions: List[DataSourceSuggestion], edge):
        """Add data source suggestions based on relationships."""
        try:
            # Suggest data quality monitoring for foreign key relationships
            if edge.connection_type.value == "foreign_key":
                suggestion = DataSourceSuggestion(
                    id=str(uuid.uuid4()),
                    suggested_source=f"Data_Quality_Monitor_{edge.source_collection}_{edge.target_collection}",
                    source_type="Monitoring Tool",
                    business_value="Ensure referential integrity and data quality",
                    enrichment_potential=0.9,
                    related_collections=[edge.source_collection, edge.target_collection],
                    suggested_columns=["integrity_status", "quality_score", "last_validated"],
                    implementation_complexity="medium",
                    priority="high",
                    created_at=datetime.utcnow()
                )
                suggestions.append(suggestion)
                
        except Exception as e:
            logger.error(f"Error adding relationship-based suggestions: {str(e)}")
    
    def _add_relationship_based_actions(self, actions: List[BusinessActionRecommendation], edge):
        """Add business actions based on relationships."""
        try:
            # Add data governance action for important relationships
            if edge.confidence_score >= 0.8:
                action = BusinessActionRecommendation(
                    id=str(uuid.uuid4()),
                    action_type="Data Governance",
                    title=f"Implement Data Governance for {edge.source_collection}-{edge.target_collection}",
                    description=f"Establish governance policies for the high-confidence relationship between {edge.source_collection} and {edge.target_collection}",
                    business_impact="Improved data quality and compliance",
                    confidence_level="high",
                    implementation_steps=[
                        "Define data ownership",
                        "Establish quality standards",
                        "Implement monitoring",
                        "Create documentation"
                    ],
                    estimated_effort="medium",
                    priority="high",
                    related_patterns=[f"High-confidence relationship: {edge.connection_type.value}"],
                    created_at=datetime.utcnow()
                )
                actions.append(action)
                
        except Exception as e:
            logger.error(f"Error adding relationship-based actions: {str(e)}")
    
    def _get_edges_for_collections(self, collection_names: List[str]) -> List:
        """Get edges for the specified collections."""
        try:
            query = {
                "$or": [
                    {"source_collection": {"$in": collection_names}},
                    {"target_collection": {"$in": collection_names}}
                ],
                "status": "active"
            }
            
            edges = list(self.mongodb_connector.db.edges.find(query))
            return edges
            
        except Exception as e:
            logger.error(f"Error getting edges for collections: {str(e)}")
            return []
    
    # Database operations
    def _store_ontology(self, ontology: BusinessOntology):
        """Store ontology in MongoDB."""
        try:
            ontology_dict = ontology.model_dump()
            self.mongodb_connector.db.business_ontologies.insert_one(ontology_dict)
        except Exception as e:
            logger.error(f"Error storing ontology {ontology.id}: {str(e)}")
    
    def _store_suggestion(self, suggestion: DataSourceSuggestion):
        """Store data source suggestion in MongoDB."""
        try:
            suggestion_dict = suggestion.model_dump()
            suggestion_dict["status"] = "pending"  # Add status field
            self.mongodb_connector.db.data_source_suggestions.insert_one(suggestion_dict)
        except Exception as e:
            logger.error(f"Error storing suggestion {suggestion.id}: {str(e)}")
    
    def _store_action(self, action: BusinessActionRecommendation):
        """Store business action in MongoDB."""
        try:
            action_dict = action.model_dump()
            action_dict["status"] = "pending"  # Add status field
            self.mongodb_connector.db.business_actions.insert_one(action_dict)
        except Exception as e:
            logger.error(f"Error storing action {action.id}: {str(e)}")
    
    def _store_explanation(self, explanation: ComplexRelationshipExplanation):
        """Store relationship explanation in MongoDB."""
        try:
            explanation_dict = explanation.model_dump()
            self.mongodb_connector.db.relationship_explanations.insert_one(explanation_dict)
        except Exception as e:
            logger.error(f"Error storing explanation {explanation.id}: {str(e)}")
    
    def _get_ontologies_from_db(self, domain: Optional[str] = None) -> List[BusinessOntology]:
        """Get ontologies from MongoDB."""
        try:
            query = {}
            if domain:
                query["domain"] = domain
            
            docs = list(self.mongodb_connector.db.business_ontologies.find(query))
            return [BusinessOntology(**doc) for doc in docs]
        except Exception as e:
            logger.error(f"Error getting ontologies from DB: {str(e)}")
            return []
    
    def _get_suggestions_from_db(self, collection_name: Optional[str] = None) -> List[DataSourceSuggestion]:
        """Get data source suggestions from MongoDB."""
        try:
            query = {}
            if collection_name:
                query["related_collections"] = collection_name
            
            docs = list(self.mongodb_connector.db.data_source_suggestions.find(query))
            return [DataSourceSuggestion(**doc) for doc in docs]
        except Exception as e:
            logger.error(f"Error getting suggestions from DB: {str(e)}")
            return []
    
    def _get_actions_from_db(self, action_type: Optional[str] = None) -> List[BusinessActionRecommendation]:
        """Get business actions from MongoDB."""
        try:
            query = {}
            if action_type:
                query["action_type"] = action_type
            
            docs = list(self.mongodb_connector.db.business_actions.find(query))
            return [BusinessActionRecommendation(**doc) for doc in docs]
        except Exception as e:
            logger.error(f"Error getting actions from DB: {str(e)}")
            return []
    
    def _get_explanations_from_db(self, collection_name: Optional[str] = None) -> List[ComplexRelationshipExplanation]:
        """Get relationship explanations from MongoDB."""
        try:
            # For now, return all explanations since they don't have collection-specific fields
            # This could be enhanced in the future
            docs = list(self.mongodb_connector.db.relationship_explanations.find({}))
            return [ComplexRelationshipExplanation(**doc) for doc in docs]
        except Exception as e:
            logger.error(f"Error getting explanations from DB: {str(e)}")
            return []
