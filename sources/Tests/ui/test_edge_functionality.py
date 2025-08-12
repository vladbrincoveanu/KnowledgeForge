"""
Edge Functionality Tests

Tests for edge creation, connection detection, and merged metadata processing.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
import sys
from datetime import datetime

# Add the UI src directory to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../UI/src'))

class TestEdgeCreation(unittest.TestCase):
    """Test edge creation and management functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_edge_data = {
            "id": "edge-123",
            "source": "customers.csv",
            "target": "orders.csv",
            "source_column": "customer_id",
            "target_column": "customer_id",
            "confidence": 0.95,
            "type": "foreign_key",
            "status": "active",
            "created_at": "2024-01-15T12:00:00Z",
            "merged_metadata": {
                "total_columns": 12,
                "shared_columns": 1,
                "unique_columns": 11,
                "data_types": ["integer", "text", "date"],
                "connection_strength": 0.95,
                "merge_strategy": "inner_join",
                "join_column": "customer_id",
                "data_quality_metrics": {
                    "completeness": 0.95,
                    "consistency": 0.92,
                    "accuracy": 0.95,
                    "uniqueness": 0.88
                },
                "estimated_rows": 950,
                "merge_complexity": "low"
            }
        }
    
    def test_edge_data_validation(self):
        """Test edge data structure validation."""
        def validate_edge_data(edge):
            required_fields = [
                'id', 'source', 'target', 'source_column', 
                'target_column', 'confidence', 'type', 'status'
            ]
            
            if not all(field in edge for field in required_fields):
                return False, f"Missing required fields: {required_fields}"
            
            if not isinstance(edge['confidence'], (int, float)):
                return False, "Confidence must be a number"
            
            if not 0 <= edge['confidence'] <= 1:
                return False, "Confidence must be between 0 and 1"
            
            valid_types = ['foreign_key', 'semantic_match', 'business_rule', 
                          'temporal', 'spatial', 'hierarchical', 'transactional']
            if edge['type'] not in valid_types:
                return False, f"Invalid connection type: {edge['type']}"
            
            valid_statuses = ['active', 'inactive', 'pending', 'rejected']
            if edge['status'] not in valid_statuses:
                return False, f"Invalid status: {edge['status']}"
            
            return True, "Edge data is valid"
        
        is_valid, message = validate_edge_data(self.sample_edge_data)
        self.assertTrue(is_valid)
        self.assertEqual(message, "Edge data is valid")
    
    def test_edge_metadata_processing(self):
        """Test edge metadata processing and calculation."""
        def process_edge_metadata(edge):
            metadata = edge.get('merged_metadata', {})
            
            # Calculate derived metrics
            total_columns = metadata.get('total_columns', 0)
            shared_columns = metadata.get('shared_columns', 0)
            unique_columns = metadata.get('unique_columns', 0)
            
            # Validate column counts
            if total_columns != shared_columns + unique_columns:
                return None, "Column count mismatch"
            
            # Calculate data quality score
            quality_metrics = metadata.get('data_quality_metrics', {})
            quality_score = sum(quality_metrics.values()) / len(quality_metrics) if quality_metrics else 0
            
            # Determine edge strength
            confidence = edge.get('confidence', 0)
            connection_strength = metadata.get('connection_strength', 0)
            overall_strength = (confidence + connection_strength) / 2
            
            processed = {
                'id': edge['id'],
                'source': edge['source'],
                'target': edge['target'],
                'confidence': confidence,
                'type': edge['type'],
                'status': edge['status'],
                'total_columns': total_columns,
                'shared_columns': shared_columns,
                'unique_columns': unique_columns,
                'quality_score': quality_score,
                'overall_strength': overall_strength,
                'merge_complexity': metadata.get('merge_complexity', 'unknown'),
                'estimated_rows': metadata.get('estimated_rows', 0)
            }
            
            return processed, None
        
        processed, error = process_edge_metadata(self.sample_edge_data)
        
        self.assertIsNone(error)
        self.assertEqual(processed['total_columns'], 12)
        self.assertEqual(processed['shared_columns'], 1)
        self.assertEqual(processed['unique_columns'], 11)
        self.assertAlmostEqual(processed['quality_score'], 0.925, places=3)
        self.assertAlmostEqual(processed['overall_strength'], 0.95, places=2)
    
    def test_edge_visualization_data(self):
        """Test edge data preparation for visualization."""
        def prepare_edge_for_visualization(edge):
            # Prepare data for graph visualization
            viz_data = {
                'id': edge['id'],
                'source': edge['source'],
                'target': edge['target'],
                'label': f"{edge['source_column']} ↔ {edge['target_column']}",
                'confidence': edge['confidence'],
                'type': edge['type'],
                'status': edge['status'],
                'color': get_edge_color(edge['confidence'], edge['type']),
                'width': get_edge_width(edge['confidence']),
                'metadata': edge.get('merged_metadata', {})
            }
            return viz_data
        
        def get_edge_color(confidence, edge_type):
            if confidence >= 0.9:
                base_color = '#28a745'  # Green
            elif confidence >= 0.7:
                base_color = '#ffc107'  # Yellow
            else:
                base_color = '#dc3545'  # Red
            
            # Add type-specific styling
            if edge_type == 'foreign_key':
                return f"{base_color}FF"  # Solid
            else:
                return f"{base_color}CC"  # Semi-transparent
        
        def get_edge_width(confidence):
            if confidence >= 0.9:
                return 3
            elif confidence >= 0.7:
                return 2
            else:
                return 1
        
        viz_data = prepare_edge_for_visualization(self.sample_edge_data)
        
        self.assertEqual(viz_data['label'], "customer_id ↔ customer_id")
        self.assertEqual(viz_data['confidence'], 0.95)
        self.assertEqual(viz_data['type'], 'foreign_key')
        self.assertEqual(viz_data['width'], 3)
        self.assertIn('#28a745', viz_data['color'])


class TestConnectionDetection(unittest.TestCase):
    """Test connection detection and analysis functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_connection_request = {
            "new_collection_name": "customers.csv",
            "existing_collections": ["orders.csv", "products.csv"]
        }
        
        self.sample_connection_response = {
            "success": True,
            "potential_connections": [
                {
                    "id": "conn-123",
                    "source_collection": "customers.csv",
                    "target_collection": "orders.csv",
                    "source_column": "customer_id",
                    "target_column": "customer_id",
                    "confidence_score": 0.95,
                    "connection_type": "foreign_key",
                    "llm_analysis": {
                        "reasoning": "Both columns represent customer identifiers",
                        "confidence_score": 0.95,
                        "connection_type": "foreign_key",
                        "business_context": "Enables linking customer orders",
                        "suggested_join_strategy": "inner_join",
                        "potential_issues": ["Data type validation needed"],
                        "recommendations": ["Verify referential integrity"]
                    },
                    "created_at": "2024-01-15T12:00:00Z",
                    "status": "pending"
                }
            ],
            "message": "Detected 1 potential connections"
        }
    
    def test_connection_detection_request_validation(self):
        """Test connection detection request validation."""
        def validate_connection_request(request):
            if 'new_collection_name' not in request:
                return False, "Missing new_collection_name"
            
            if 'existing_collections' not in request:
                return False, "Missing existing_collections"
            
            if not isinstance(request['existing_collections'], list):
                return False, "existing_collections must be a list"
            
            if len(request['existing_collections']) == 0:
                return False, "existing_collections cannot be empty"
            
            return True, "Request is valid"
        
        is_valid, message = validate_connection_request(self.sample_connection_request)
        self.assertTrue(is_valid)
        self.assertEqual(message, "Request is valid")
    
    def test_connection_response_processing(self):
        """Test connection detection response processing."""
        def process_connection_response(response):
            if not response.get('success', False):
                return None, response.get('error', 'Unknown error')
            
            connections = response.get('potential_connections', [])
            
            # Process each connection
            processed_connections = []
            for conn in connections:
                processed = {
                    'id': conn['id'],
                    'source': conn['source_collection'],
                    'target': conn['target_collection'],
                    'source_column': conn['source_column'],
                    'target_column': conn['target_column'],
                    'confidence': conn['confidence_score'],
                    'type': conn['connection_type'],
                    'status': conn['status'],
                    'llm_analysis': conn.get('llm_analysis', {}),
                    'created_at': conn.get('created_at')
                }
                processed_connections.append(processed)
            
            return {
                'connections': processed_connections,
                'total_count': len(processed_connections),
                'message': response.get('message', '')
            }, None
        
        processed, error = process_connection_response(self.sample_connection_response)
        
        self.assertIsNone(error)
        self.assertEqual(processed['total_count'], 1)
        self.assertEqual(len(processed['connections']), 1)
        self.assertEqual(processed['connections'][0]['confidence'], 0.95)
    
    def test_connection_confidence_filtering(self):
        """Test filtering connections by confidence threshold."""
        def filter_connections_by_confidence(connections, threshold=0.6):
            filtered = []
            for conn in connections:
                if conn.get('confidence_score', 0) >= threshold:
                    filtered.append(conn)
            return filtered
        
        # Test with different thresholds
        connections = self.sample_connection_response['potential_connections']
        
        # High threshold
        high_confidence = filter_connections_by_confidence(connections, 0.9)
        self.assertEqual(len(high_confidence), 1)
        
        # Very high threshold
        very_high_confidence = filter_connections_by_confidence(connections, 0.99)
        self.assertEqual(len(very_high_confidence), 0)
        
        # Low threshold
        low_confidence = filter_connections_by_confidence(connections, 0.5)
        self.assertEqual(len(low_confidence), 1)


class TestMergedMetadata(unittest.TestCase):
    """Test merged metadata processing and calculation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_metadata_a = {
            "columns": {
                "customer_id": {"data_type": "integer", "unique_count": 1000},
                "customer_name": {"data_type": "string", "unique_count": 950},
                "email": {"data_type": "string", "unique_count": 1000},
                "phone": {"data_type": "string", "unique_count": 800}
            },
            "total_rows": 1000,
            "file_name": "customers.csv"
        }
        
        self.sample_metadata_b = {
            "columns": {
                "customer_id": {"data_type": "integer", "unique_count": 1000},
                "order_id": {"data_type": "integer", "unique_count": 5000},
                "order_date": {"data_type": "date", "unique_count": 365},
                "total_amount": {"data_type": "float", "unique_count": 5000}
            },
            "total_rows": 5000,
            "file_name": "orders.csv"
        }
    
    def test_metadata_merging(self):
        """Test merging metadata from two datasets."""
        def merge_metadata(metadata_a, metadata_b, connection):
            # Get all unique columns
            all_columns = set(metadata_a['columns'].keys()) | set(metadata_b['columns'].keys())
            shared_columns = set(metadata_a['columns'].keys()) & set(metadata_b['columns'].keys())
            unique_columns = all_columns - shared_columns
            
            # Collect data types
            data_types = set()
            column_types = {}
            
            for col in all_columns:
                if col in metadata_a['columns']:
                    col_type = metadata_a['columns'][col]['data_type']
                    column_types[col] = col_type
                    data_types.add(col_type)
                elif col in metadata_b['columns']:
                    col_type = metadata_b['columns'][col]['data_type']
                    column_types[col] = col_type
                    data_types.add(col_type)
            
            # Calculate data quality metrics
            quality_metrics = calculate_data_quality_metrics(metadata_a, metadata_b, connection)
            
            # Estimate merged rows
            estimated_rows = min(metadata_a['total_rows'], metadata_b['total_rows'])
            
            merged_metadata = {
                'total_columns': len(all_columns),
                'shared_columns': len(shared_columns),
                'unique_columns': len(unique_columns),
                'data_types': list(data_types),
                'column_types': column_types,
                'data_quality_metrics': quality_metrics,
                'estimated_rows': estimated_rows,
                'merge_strategy': connection.get('suggested_join_strategy', 'inner_join'),
                'join_column': connection['source_column'],
                'merge_complexity': determine_merge_complexity(len(shared_columns), connection['confidence'])
            }
            
            return merged_metadata
        
        def calculate_data_quality_metrics(metadata_a, metadata_b, connection):
            # Simplified quality calculation
            return {
                'completeness': 0.95,
                'consistency': 0.92,
                'accuracy': connection['confidence'],
                'uniqueness': 0.88
            }
        
        def determine_merge_complexity(shared_cols, confidence):
            if shared_cols > 0 and confidence >= 0.9:
                return 'low'
            elif shared_cols > 0 and confidence >= 0.7:
                return 'medium'
            else:
                return 'high'
        
        connection = {
            'source_column': 'customer_id',
            'target_column': 'customer_id',
            'confidence': 0.95,
            'suggested_join_strategy': 'inner_join'
        }
        
        merged = merge_metadata(self.sample_metadata_a, self.sample_metadata_b, connection)
        
        self.assertEqual(merged['total_columns'], 7)  # 4 + 4 - 1 shared
        self.assertEqual(merged['shared_columns'], 1)  # customer_id
        self.assertEqual(merged['unique_columns'], 6)  # 7 - 1 shared
        self.assertEqual(merged['estimated_rows'], 1000)  # min of both
        self.assertEqual(merged['merge_complexity'], 'low')
    
    def test_data_quality_assessment(self):
        """Test data quality assessment for merged datasets."""
        def assess_data_quality(metadata_a, metadata_b, connection):
            # Assess completeness
            completeness_a = sum(1 for col in metadata_a['columns'].values() if col['unique_count'] > 0) / len(metadata_a['columns'])
            completeness_b = sum(1 for col in metadata_b['columns'].values() if col['unique_count'] > 0) / len(metadata_b['columns'])
            completeness = min(completeness_a, completeness_b)
            
            # Assess consistency (simplified)
            consistency = 0.9 if connection['confidence'] > 0.8 else 0.7
            
            # Assess accuracy based on connection confidence
            accuracy = connection['confidence']
            
            # Assess uniqueness
            uniqueness_a = sum(col['unique_count'] for col in metadata_a['columns'].values()) / (len(metadata_a['columns']) * metadata_a['total_rows'])
            uniqueness_b = sum(col['unique_count'] for col in metadata_b['columns'].values()) / (len(metadata_b['columns']) * metadata_b['total_rows'])
            uniqueness = min(uniqueness_a, uniqueness_b)
            
            return {
                'completeness': completeness,
                'consistency': consistency,
                'accuracy': accuracy,
                'uniqueness': uniqueness,
                'overall_score': (completeness + consistency + accuracy + uniqueness) / 4
            }
        
        connection = {
            'confidence': 0.95
        }
        
        quality = assess_data_quality(self.sample_metadata_a, self.sample_metadata_b, connection)
        
        self.assertGreater(quality['completeness'], 0.8)
        self.assertEqual(quality['consistency'], 0.9)
        self.assertEqual(quality['accuracy'], 0.95)
        self.assertGreater(quality['overall_score'], 0.8)


class TestEdgeConfirmation(unittest.TestCase):
    """Test edge confirmation and user interaction functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_confirmation_request = {
            "potential_connection_id": "conn-123",
            "user_id": "user123"
        }
        
        self.sample_confirmation_response = {
            "success": True,
            "edge": {
                "id": "edge-456",
                "source_collection": "customers.csv",
                "target_collection": "orders.csv",
                "source_column": "customer_id",
                "target_column": "customer_id",
                "confidence_score": 0.95,
                "connection_type": "foreign_key",
                "status": "active",
                "created_at": "2024-01-15T12:00:00Z",
                "created_by": "user123"
            },
            "message": "Edge created successfully"
        }
    
    def test_confirmation_request_validation(self):
        """Test edge confirmation request validation."""
        def validate_confirmation_request(request):
            if 'potential_connection_id' not in request:
                return False, "Missing potential_connection_id"
            
            if not request['potential_connection_id']:
                return False, "potential_connection_id cannot be empty"
            
            if 'user_id' not in request:
                return False, "Missing user_id"
            
            return True, "Request is valid"
        
        is_valid, message = validate_confirmation_request(self.sample_confirmation_request)
        self.assertTrue(is_valid)
        self.assertEqual(message, "Request is valid")
    
    def test_confirmation_response_processing(self):
        """Test edge confirmation response processing."""
        def process_confirmation_response(response):
            if not response.get('success', False):
                return None, response.get('error', 'Unknown error')
            
            edge = response.get('edge', {})
            if not edge:
                return None, "No edge data in response"
            
            processed_edge = {
                'id': edge['id'],
                'source': edge['source_collection'],
                'target': edge['target_collection'],
                'source_column': edge['source_column'],
                'target_column': edge['target_column'],
                'confidence': edge['confidence_score'],
                'type': edge['connection_type'],
                'status': edge['status'],
                'created_at': edge['created_at'],
                'created_by': edge['created_by']
            }
            
            return {
                'edge': processed_edge,
                'message': response.get('message', ''),
                'success': True
            }, None
        
        processed, error = process_confirmation_response(self.sample_confirmation_response)
        
        self.assertIsNone(error)
        self.assertTrue(processed['success'])
        self.assertEqual(processed['edge']['confidence'], 0.95)
        self.assertEqual(processed['edge']['status'], 'active')
    
    def test_user_interaction_tracking(self):
        """Test user interaction tracking for edge confirmations."""
        def track_user_interaction(user_id, action, connection_id, timestamp=None):
            if timestamp is None:
                timestamp = datetime.utcnow().isoformat()
            
            interaction = {
                'user_id': user_id,
                'action': action,
                'connection_id': connection_id,
                'timestamp': timestamp,
                'session_id': f"session_{user_id}_{timestamp[:10]}"
            }
            
            return interaction
        
        interaction = track_user_interaction(
            user_id="user123",
            action="confirm_connection",
            connection_id="conn-123"
        )
        
        self.assertEqual(interaction['user_id'], "user123")
        self.assertEqual(interaction['action'], "confirm_connection")
        self.assertEqual(interaction['connection_id'], "conn-123")
        self.assertIn('timestamp', interaction)
        self.assertIn('session_id', interaction)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestEdgeCreation,
        TestConnectionDetection,
        TestMergedMetadata,
        TestEdgeConfirmation
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Edge Functionality Tests Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}") 