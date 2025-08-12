"""
Connection Detection Service

Service for detecting potential connections between datasets using LLM analysis.
"""

import uuid
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from ...Domain.models import (
    PotentialConnection, Edge, MergedMetadata, LLMAnalysisResult,
    ConnectionType, ConnectionDetectionRequest, ConnectionDetectionResponse,
    EdgeConfirmationRequest, EdgeConfirmationResponse, FileMetadata
)
from ...Infrastructure.mongodb_connector import MongoDBConnector
from ...Infrastructure.llm_analyzer import LLMAnalyzer

logger = logging.getLogger(__name__)


class ConnectionDetectionService:
    """Service for detecting connections between datasets using LLM analysis."""
    
    def __init__(self, mongodb_connector: MongoDBConnector, llm_analyzer: LLMAnalyzer):
        self.mongodb_connector = mongodb_connector
        self.llm_analyzer = llm_analyzer
        self.confidence_threshold = 0.7  # Increased threshold for better quality
        self.max_connections_per_pair = 3  # Limit connections per collection pair
    
    def detect_connections(self, request: ConnectionDetectionRequest) -> ConnectionDetectionResponse:
        """
        DISABLED: Old connection detection system removed.
        New system uses frontend LLM analysis only.
        
        Args:
            request: Connection detection request
            
        Returns:
            ConnectionDetectionResponse with no connections
        """
        logger.info(f"Connection detection DISABLED for: {request.new_collection_name}")
        
        return ConnectionDetectionResponse(
            success=True,
            potential_connections=[],
            message="Connection detection disabled - using new AI-powered frontend system",
            error=None
        )
    
    def confirm_connection(self, request: EdgeConfirmationRequest) -> EdgeConfirmationResponse:
        """
        Confirm a potential connection and create an edge.
        
        Args:
            request: Edge confirmation request
            
        Returns:
            EdgeConfirmationResponse with the created edge
        """
        try:
            logger.info(
                f"Confirming connection; potential_connection_id={request.potential_connection_id}"
            )

            # Try legacy flow: fetch potential connection from DB
            potential_connection = None
            if request.potential_connection_id:
                potential_connection = self._get_potential_connection(
                    request.potential_connection_id
                )

            # If not found, but a direct connection payload is provided, build a PotentialConnection
            if not potential_connection and request.connection:
                logger.info("No stored potential connection found; using direct connection payload from request")
                pc_payload = request.connection

                # Build LLMAnalysisResult with safe defaults
                llm_analysis = LLMAnalysisResult(
                    reasoning=(pc_payload.get("llm_analysis", {}) or {}).get(
                        "reasoning", "Connection analysis provided"
                    ),
                    confidence_score=float(
                        pc_payload.get("confidence_score")
                        or pc_payload.get("ai_score")
                        or pc_payload.get("confidence")
                        or 0.75
                    ),
                    connection_type=ConnectionType(
                        (pc_payload.get("connection_type") or "foreign_key").lower()
                    ),
                    business_context=(pc_payload.get("llm_analysis", {}) or {}).get(
                        "business_context", ""
                    ),
                    suggested_join_strategy=(pc_payload.get("llm_analysis", {}) or {}).get(
                        "suggested_join_strategy", "inner_join"
                    ),
                    potential_issues=(pc_payload.get("llm_analysis", {}) or {}).get(
                        "potential_issues", []
                    ),
                    recommendations=(pc_payload.get("llm_analysis", {}) or {}).get(
                        "recommendations", []
                    ),
                )

                potential_connection = PotentialConnection(
                    id=pc_payload.get("id") or str(uuid.uuid4()),
                    source_collection=pc_payload.get("source_collection")
                    or pc_payload.get("source"),
                    target_collection=pc_payload.get("target_collection")
                    or pc_payload.get("target"),
                    source_column=pc_payload.get("source_column")
                    or pc_payload.get("columnA"),
                    target_column=pc_payload.get("target_column")
                    or pc_payload.get("columnB"),
                    confidence_score=float(
                        pc_payload.get("confidence_score")
                        or pc_payload.get("ai_score")
                        or pc_payload.get("confidence")
                        or 0.75
                    ),
                    connection_type=llm_analysis.connection_type,
                    llm_analysis=llm_analysis,
                    created_at=datetime.utcnow(),
                    status="pending",
                )

            if not potential_connection:
                return EdgeConfirmationResponse(
                    success=False,
                    edge=None,
                    message="Potential connection not found and no direct payload provided",
                    error="Invalid confirmation request",
                )

            # Create merged metadata
            merged_metadata = self._create_merged_metadata(potential_connection)

            # If UI provided corrected/augmented metadata, merge it in place
            if request.corrected_metadata and isinstance(merged_metadata, MergedMetadata):
                try:
                    # Non-destructive merge for known fields
                    cm = request.corrected_metadata
                    if "merge_strategy" in cm:
                        merged_metadata.merge_strategy = cm["merge_strategy"]
                    if "join_column" in cm:
                        merged_metadata.join_column = cm["join_column"]
                    if "data_quality_metrics" in cm and isinstance(cm["data_quality_metrics"], dict):
                        merged_metadata.data_quality_metrics.update(cm["data_quality_metrics"])
                except Exception as merge_err:
                    logger.warning(f"Failed to merge corrected metadata: {merge_err}")

            # Create the edge
            edge = Edge(
                id=str(uuid.uuid4()),
                source_collection=potential_connection.source_collection,
                target_collection=potential_connection.target_collection,
                source_column=potential_connection.source_column,
                target_column=potential_connection.target_column,
                confidence_score=potential_connection.confidence_score,
                connection_type=potential_connection.connection_type,
                merged_metadata=merged_metadata,
                llm_analysis=potential_connection.llm_analysis,
                status="active",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                created_by=request.user_id,
            )

            # Store the edge in MongoDB
            self._store_edge(edge)

            # Update potential connection status (legacy flow only)
            if request.potential_connection_id:
                self._update_potential_connection_status(
                    request.potential_connection_id, "accepted"
                )

            logger.info(f"Created edge: {edge.id}")

            return EdgeConfirmationResponse(
                success=True,
                edge=edge,
                message="Edge created successfully",
                error=None,
            )

        except Exception as e:
            logger.error(f"Error confirming connection: {str(e)}")
            return EdgeConfirmationResponse(
                success=False,
                edge=None,
                message="Failed to confirm connection",
                error=str(e)
            )
    
    def get_potential_connections(self, collection_name: Optional[str] = None) -> List[PotentialConnection]:
        """
        DISABLED: Old potential connections system removed.
        New system uses frontend LLM analysis only.
        
        Args:
            collection_name: Optional collection name to filter by
            
        Returns:
            Empty list - no more pending connections
        """
        logger.info("Potential connections DISABLED - using new AI-powered frontend system")
        return []
    
    def get_edges(self, collection_name: Optional[str] = None) -> List[Edge]:
        """
        Get confirmed edges, optionally filtered by collection.
        
        Args:
            collection_name: Optional collection name to filter by
            
        Returns:
            List of edges
        """
        try:
            return self._get_edges_from_db(collection_name)
        except Exception as e:
            logger.error(f"Error getting edges: {str(e)}")
            return []
    
    def _analyze_potential_connections(
        self, 
        new_collection_metadata: FileMetadata, 
        existing_metadata: Dict[str, FileMetadata],
        new_collection_name: str
    ) -> List[PotentialConnection]:
        """Analyze potential connections using LLM."""
        potential_connections = []
        
        # Use ThreadPoolExecutor for parallel analysis
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_collection = {}
            
            for collection_name, metadata in existing_metadata.items():
                future = executor.submit(
                    self._analyze_collection_pair,
                    new_collection_metadata,
                    metadata,
                    collection_name,
                    new_collection_name
                )
                future_to_collection[future] = collection_name
            
            # Collect results
            for future in as_completed(future_to_collection):
                try:
                    connections = future.result()
                    potential_connections.extend(connections)
                except Exception as e:
                    collection_name = future_to_collection[future]
                    logger.error(f"Error analyzing collection {collection_name}: {str(e)}")
        
        return potential_connections
    
    def _analyze_collection_pair(
        self, 
        new_metadata: FileMetadata, 
        existing_metadata: FileMetadata,
        existing_collection_name: str,
        new_collection_name: str = None
    ) -> List[PotentialConnection]:
        """Analyze potential connections between two collections."""
        connections = []
        
        # Get column names from both collections
        new_columns = list(new_metadata.columns.keys())
        existing_columns = list(existing_metadata.columns.keys())
        
        # Pre-filter columns to reduce analysis load
        candidate_pairs = self._get_candidate_column_pairs(new_columns, existing_columns)
        
        # Analyze only the most promising column pairs
        analyzed_pairs = []
        for new_col, existing_col in candidate_pairs:
            # Skip if already analyzed
            if self._connection_exists(new_metadata.file_info.file_name, existing_collection_name, new_col, existing_col):
                continue
            
            # Analyze the column pair using LLM
            llm_analysis = self._analyze_column_pair(
                new_metadata, existing_metadata, new_col, existing_col
            )
            
            # Only create potential connection if confidence is above threshold
            if llm_analysis.confidence_score >= self.confidence_threshold:
                # Use the collection name from the request instead of file name
                source_collection_name = new_collection_name or new_metadata.file_info.file_name
                connection = PotentialConnection(
                    id=str(uuid.uuid4()),
                    source_collection=source_collection_name,
                    target_collection=existing_collection_name,
                    source_column=new_col,
                    target_column=existing_col,
                    confidence_score=llm_analysis.confidence_score,
                    connection_type=llm_analysis.connection_type,
                    llm_analysis=llm_analysis,
                    created_at=datetime.utcnow(),
                    status="pending"
                )
                analyzed_pairs.append((connection, llm_analysis.confidence_score))
        
        # Sort by confidence and take only the top connections
        analyzed_pairs.sort(key=lambda x: x[1], reverse=True)
        top_connections = analyzed_pairs[:self.max_connections_per_pair]
        
        return [conn for conn, _ in top_connections]
    
    def _get_candidate_column_pairs(self, new_columns: List[str], existing_columns: List[str]) -> List[tuple]:
        """Get candidate column pairs for analysis, prioritizing likely matches."""
        candidates = []
        
        # Priority 1: Exact name matches (case-insensitive)
        for new_col in new_columns:
            for existing_col in existing_columns:
                if new_col.lower() == existing_col.lower():
                    candidates.append((new_col, existing_col))
        
        # Priority 2: Common identifier patterns
        id_patterns = ['id', 'key', 'code', 'ref', 'num', 'no']
        for new_col in new_columns:
            for existing_col in existing_columns:
                new_lower = new_col.lower()
                existing_lower = existing_col.lower()
                
                # Check if both contain similar identifier patterns
                for pattern in id_patterns:
                    if pattern in new_lower and pattern in existing_lower:
                        # Check if they're related (e.g., customer_id and customer_id)
                        new_base = new_lower.replace(pattern, '').strip('_')
                        existing_base = existing_lower.replace(pattern, '').strip('_')
                        if new_base and existing_base and (new_base in existing_base or existing_base in new_base):
                            candidates.append((new_col, existing_col))
                            break
        
        # Priority 3: Semantic matches (e.g., customer_name vs client_name)
        semantic_pairs = [
            ('customer', 'client'), ('user', 'customer'), ('user', 'client'),
            ('order', 'purchase'), ('sale', 'order'), ('transaction', 'order'),
            ('product', 'item'), ('goods', 'product'), ('service', 'product'),
            ('date', 'created'), ('date', 'timestamp'), ('time', 'date'),
            ('email', 'mail'), ('phone', 'telephone'), ('mobile', 'phone')
        ]
        
        for new_col in new_columns:
            for existing_col in existing_columns:
                new_lower = new_col.lower()
                existing_lower = existing_col.lower()
                
                for word1, word2 in semantic_pairs:
                    if word1 in new_lower and word2 in existing_lower:
                        candidates.append((new_col, existing_col))
                        break
                    elif word2 in new_lower and word1 in existing_lower:
                        candidates.append((new_col, existing_col))
                        break
        
        # Priority 4: Limited random sampling for other columns (max 5 pairs)
        remaining_new = [col for col in new_columns if not any(col == pair[0] for pair in candidates)]
        remaining_existing = [col for col in existing_columns if not any(col == pair[1] for pair in candidates)]
        
        import random
        random_pairs = list(zip(remaining_new[:3], remaining_existing[:3]))
        candidates.extend(random_pairs)
        
        # Remove duplicates and limit total candidates
        unique_candidates = list(set(candidates))
        return unique_candidates[:10]  # Limit to 10 candidate pairs
    
    def _analyze_column_pair(
        self, 
        new_metadata: FileMetadata, 
        existing_metadata: FileMetadata,
        new_col: str, 
        existing_col: str
    ) -> LLMAnalysisResult:
        """Analyze a pair of columns using LLM."""
        
        # Prepare context for LLM analysis
        context = {
            "new_collection": {
                "name": new_metadata.file_info.file_name,
                "columns": list(new_metadata.columns.keys()),
                "total_rows": new_metadata.file_info.total_rows,
                "column_info": {
                    col: {
                        "data_type": meta.data_type.value,
                        "sample_values": meta.sample_values[:5],
                        "unique_count": meta.unique_count
                    } for col, meta in new_metadata.columns.items()
                }
            },
            "existing_collection": {
                "name": existing_metadata.file_info.file_name,
                "columns": list(existing_metadata.columns.keys()),
                "total_rows": existing_metadata.file_info.total_rows,
                "column_info": {
                    col: {
                        "data_type": meta.data_type.value,
                        "sample_values": meta.sample_values[:5],
                        "unique_count": meta.unique_count
                    } for col, meta in existing_metadata.columns.items()
                }
            },
            "column_pair": {
                "new_column": new_col,
                "existing_column": existing_col
            }
        }
        
        # Use LLM analyzer to get analysis
        return self.llm_analyzer.analyze_connection(context)
    
    def _create_merged_metadata(self, potential_connection: PotentialConnection) -> MergedMetadata:
        """Create merged metadata for a confirmed connection.

        This function is resilient to metadata being a dict (as returned from Mongo) or a domain object.
        """

        # Get metadata for both collections
        source_metadata = self._get_collection_metadata(potential_connection.source_collection)
        target_metadata = self._get_collection_metadata(potential_connection.target_collection)

        if not source_metadata or not target_metadata:
            raise ValueError("Metadata not found for one or both collections")

        # Helper to access columns dict regardless of object/dict type
        def get_columns(meta_obj):
            if isinstance(meta_obj, dict):
                return meta_obj.get("columns", {}) or {}
            return getattr(meta_obj, "columns", {}) or {}

        def get_total_rows(meta_obj) -> int:
            if isinstance(meta_obj, dict):
                return int(((meta_obj.get("file_info") or {}).get("total_rows")) or 0)
            file_info = getattr(meta_obj, "file_info", None)
            return int(getattr(file_info, "total_rows", 0) or 0)

        source_columns = get_columns(source_metadata)
        target_columns = get_columns(target_metadata)

        # Calculate merged metadata basics
        all_columns = list(set(list(source_columns.keys()) + list(target_columns.keys())))
        shared_columns = [col for col in source_columns.keys() if col in target_columns.keys()]
        unique_columns = [col for col in all_columns if col not in shared_columns]

        # Determine data types with safe defaults
        data_types = set()
        column_types = {}
        for col in all_columns:
            col_meta = source_columns.get(col) or target_columns.get(col) or {}
            if isinstance(col_meta, dict):
                col_type = (col_meta.get("data_type") or "string")
            else:
                # ColumnMetadata object
                col_type = getattr(col_meta, "data_type", "string")
                col_type = getattr(col_type, "value", col_type)
            column_types[col] = col_type
            data_types.add(col_type)

        # Data quality metrics - derive from confidence with sensible floors
        conf = float(potential_connection.confidence_score or 0.75)
        data_quality_metrics = {
            "completeness": max(0.7, min(1.0, conf)),
            "consistency": max(0.8, min(1.0, conf * 0.95)),
            "accuracy": max(0.85, min(1.0, conf)),
            "uniqueness": 0.8,
        }

        # Estimate rows using available totals when present
        try:
            estimated_rows = int(min(get_total_rows(source_metadata), get_total_rows(target_metadata)) * conf)
        except Exception:
            estimated_rows = 0

        # Determine merge complexity
        merge_complexity = self._determine_merge_complexity(conf)

        return MergedMetadata(
            total_columns=len(all_columns),
            shared_columns=len(shared_columns),
            unique_columns=len(unique_columns),
            data_types=list(data_types),
            column_types=column_types,
            connection_strength=conf,
            merge_strategy=potential_connection.llm_analysis.suggested_join_strategy,
            join_column=potential_connection.source_column,
            data_quality_metrics=data_quality_metrics,
            estimated_rows=estimated_rows,
            last_updated=datetime.utcnow(),
            merge_complexity=merge_complexity,
            # Sample data generation is optional and type-sensitive; omit for resilience
            sample_data=None,
        )
    
    def _calculate_data_quality_metrics(
        self, 
        source_metadata: FileMetadata, 
        target_metadata: FileMetadata,
        connection: PotentialConnection
    ) -> Dict[str, float]:
        """Calculate data quality metrics for the merged dataset."""
        
        # Get column metadata
        source_col = source_metadata.columns.get(connection.source_column)
        target_col = target_metadata.columns.get(connection.target_column)
        
        if not source_col or not target_col:
            return {
                "completeness": 0.8,
                "consistency": 0.8,
                "accuracy": 0.8,
                "uniqueness": 0.8
            }
        
        # Calculate metrics based on column characteristics
        completeness = 1.0 - max(source_col.null_percentage, target_col.null_percentage) / 100.0
        consistency = min(source_col.unique_count / source_col.total_count, target_col.unique_count / target_col.total_count)
        accuracy = connection.confidence_score  # Use connection confidence as accuracy proxy
        uniqueness = min(source_col.unique_count / source_col.total_count, target_col.unique_count / target_col.total_count)
        
        return {
            "completeness": max(0.7, completeness),
            "consistency": max(0.8, consistency),
            "accuracy": max(0.85, accuracy),
            "uniqueness": max(0.75, uniqueness)
        }
    
    def _determine_merge_complexity(self, confidence_score: float) -> str:
        """Determine merge complexity based on confidence score."""
        if confidence_score >= 0.9:
            return "low"
        elif confidence_score >= 0.7:
            return "medium"
        else:
            return "high"
    
    def _create_sample_merged_data(
        self, 
        source_metadata: FileMetadata, 
        target_metadata: FileMetadata
    ) -> Optional[Dict[str, Any]]:
        """Create sample merged data."""
        try:
            # Get sample data from both collections
            source_samples = []
            target_samples = []
            
            for col_name, col_meta in source_metadata.columns.items():
                if col_meta.sample_values:
                    source_samples.extend(col_meta.sample_values[:3])
            
            for col_name, col_meta in target_metadata.columns.items():
                if col_meta.sample_values:
                    target_samples.extend(col_meta.sample_values[:3])
            
            if not source_samples and not target_samples:
                return None
            
            # Create sample merged data
            merged_columns = list(source_metadata.columns.keys()) + [
                col for col in target_metadata.columns.keys() 
                if col not in source_metadata.columns.keys()
            ]
            
            # Create sample rows (simplified)
            sample_rows = []
            for i in range(min(3, len(source_samples), len(target_samples))):
                row = []
                for col in merged_columns:
                    if col in source_metadata.columns and i < len(source_samples):
                        row.append(str(source_samples[i]))
                    elif col in target_metadata.columns and i < len(target_samples):
                        row.append(str(target_samples[i]))
                    else:
                        row.append("")
                sample_rows.append(row)
            
            return {
                "columns": merged_columns,
                "rows": sample_rows
            }
            
        except Exception as e:
            logger.error(f"Error creating sample merged data: {str(e)}")
            return None
    
    # Database operations
    def _get_collection_metadata(self, collection_name: str) -> Optional[FileMetadata]:
        """Get metadata for a collection from MongoDB."""
        try:
            collection_info = self.mongodb_connector.get_collection_info(collection_name)
            if collection_info and collection_info.metadata:
                return collection_info.metadata
            return None
        except Exception as e:
            logger.error(f"Error getting collection metadata: {str(e)}")
            return None
    
    def _connection_exists(
        self, 
        source_collection: str, 
        target_collection: str, 
        source_column: str, 
        target_column: str
    ) -> bool:
        """Check if a connection already exists."""
        try:
            # Check potential connections
            potential_connections = self._get_potential_connections_from_db()
            for conn in potential_connections:
                if (conn.source_collection == source_collection and 
                    conn.target_collection == target_collection and
                    conn.source_column == source_column and
                    conn.target_column == target_column):
                    return True
            
            # Check confirmed edges
            edges = self._get_edges_from_db()
            for edge in edges:
                if (edge.source_collection == source_collection and 
                    edge.target_collection == target_collection and
                    edge.source_column == source_column and
                    edge.target_column == target_column):
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking connection existence: {str(e)}")
            return False
    
    def _store_potential_connections(self, connections: List[PotentialConnection]):
        """Store potential connections in MongoDB."""
        try:
            for connection in connections:
                # Convert enum to string for MongoDB storage
                connection_dict = connection.model_dump()
                connection_dict['connection_type'] = connection.connection_type.value
                
                # Also convert nested enum in llm_analysis
                if 'llm_analysis' in connection_dict and connection_dict['llm_analysis']:
                    if 'connection_type' in connection_dict['llm_analysis']:
                        connection_dict['llm_analysis']['connection_type'] = connection_dict['llm_analysis']['connection_type'].value
                
                self.mongodb_connector.db.potential_connections.insert_one(connection_dict)
        except Exception as e:
            logger.error(f"Error storing potential connections: {str(e)}")
    
    def _get_potential_connection(self, connection_id: str) -> Optional[PotentialConnection]:
        """Get a potential connection by ID."""
        try:
            doc = self.mongodb_connector.db.potential_connections.find_one({"id": connection_id})
            if doc:
                return PotentialConnection(**doc)
            return None
        except Exception as e:
            logger.error(f"Error getting potential connection: {str(e)}")
            return None
    
    def _get_potential_connections_from_db(self, collection_name: Optional[str] = None) -> List[PotentialConnection]:
        """Get potential connections from MongoDB."""
        try:
            query = {"status": "pending"}
            if collection_name:
                query["$or"] = [
                    {"source_collection": collection_name},
                    {"target_collection": collection_name}
                ]
            
            docs = self.mongodb_connector.db.potential_connections.find(query)
            return [PotentialConnection(**doc) for doc in docs]
        except Exception as e:
            logger.error(f"Error getting potential connections from DB: {str(e)}")
            return []
    
    def _update_potential_connection_status(self, connection_id: str, status: str):
        """Update potential connection status."""
        try:
            self.mongodb_connector.db.potential_connections.update_one(
                {"id": connection_id},
                {"$set": {"status": status}}
            )
        except Exception as e:
            logger.error(f"Error updating potential connection status: {str(e)}")
    
    def _store_edge(self, edge: Edge):
        """Store edge in MongoDB."""
        try:
            # Convert enums to strings for MongoDB
            edge_doc = edge.model_dump()
            if isinstance(edge.connection_type, ConnectionType):
                edge_doc["connection_type"] = edge.connection_type.value
            # Nested llm_analysis.connection_type may also be an enum
            if edge_doc.get("llm_analysis") and isinstance(edge.llm_analysis.connection_type, ConnectionType):
                edge_doc["llm_analysis"]["connection_type"] = edge.llm_analysis.connection_type.value

            self.mongodb_connector.db.edges.insert_one(edge_doc)
        except Exception as e:
            logger.error(f"Error storing edge: {str(e)}")
    
    def _get_edges_from_db(self, collection_name: Optional[str] = None) -> List[Edge]:
        """Get edges from MongoDB."""
        try:
            query = {"status": "active"}
            if collection_name:
                query["$or"] = [
                    {"source_collection": collection_name},
                    {"target_collection": collection_name}
                ]
            
            docs = list(self.mongodb_connector.db.edges.find(query))
            edges: List[Edge] = []
            for doc in docs:
                try:
                    edges.append(Edge(**doc))
                except Exception as conv_err:
                    logger.error(f"Skipping edge due to conversion error: {conv_err}; doc id={doc.get('id')}" )
                    continue
            return edges
        except Exception as e:
            logger.error(f"Error getting edges from DB: {str(e)}")
            return []
    
    def _cleanup_old_connections(self):
        """Clean up old pending connections to prevent buildup."""
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            # Remove pending connections older than 7 days
            result = self.mongodb_connector.db.potential_connections.delete_many({
                "status": "pending",
                "created_at": {"$lt": cutoff_date}
            })
            
            if result.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} old pending connections")
                
        except Exception as e:
            logger.error(f"Error cleaning up old connections: {str(e)}") 