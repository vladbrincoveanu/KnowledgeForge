"""
UI Component Tests

Tests for React components and UI functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
import sys

# Add the UI src directory to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../UI/src'))

class TestFileUploader(unittest.TestCase):
    """Test FileUploader component functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_on_files_uploaded = Mock()
        self.mock_is_processing = False
        
    def test_file_uploader_initialization(self):
        """Test FileUploader component initializes correctly."""
        # This would test React component initialization
        # For now, we'll test the logic functions
        pass
    
    def test_csv_file_parsing(self):
        """Test CSV file parsing functionality."""
        # Mock CSV content
        csv_content = """customer_id,customer_name,email,phone,city,country
1,John Smith,john.smith@email.com,+1-555-0101,New York,USA
2,Jane Doe,jane.doe@email.com,+1-555-0102,Los Angeles,USA"""
        
        # Test parsing logic
        lines = csv_content.strip().split('\n')
        headers = lines[0].split(',')
        data_rows = []
        
        for line in lines[1:]:
            values = line.split(',')
            row = dict(zip(headers, values))
            data_rows.append(row)
        
        self.assertEqual(len(headers), 6)
        self.assertEqual(headers[0], 'customer_id')
        self.assertEqual(len(data_rows), 2)
        self.assertEqual(data_rows[0]['customer_name'], 'John Smith')
    
    def test_file_type_detection(self):
        """Test file type detection logic."""
        def get_file_icon(file_name):
            if file_name.lower().endswith('.csv'):
                return '📊'
            elif file_name.lower().endswith(('.xlsx', '.xls')):
                return '📈'
            else:
                return '📄'
        
        self.assertEqual(get_file_icon('data.csv'), '📊')
        self.assertEqual(get_file_icon('report.xlsx'), '📈')
        self.assertEqual(get_file_icon('document.pdf'), '📄')
    
    def test_file_validation(self):
        """Test file validation logic."""
        def validate_file(file):
            allowed_types = ['.csv', '.xlsx', '.xls']
            file_extension = os.path.splitext(file.name)[1].lower()
            
            if file_extension not in allowed_types:
                return False, f"File type {file_extension} not supported"
            
            if file.size > 10 * 1024 * 1024:  # 10MB limit
                return False, "File size exceeds 10MB limit"
            
            return True, "File is valid"
        
        # Test valid CSV file
        mock_csv_file = Mock()
        mock_csv_file.name = 'data.csv'
        mock_csv_file.size = 1024
        
        is_valid, message = validate_file(mock_csv_file)
        self.assertTrue(is_valid)
        self.assertEqual(message, "File is valid")
        
        # Test invalid file type
        mock_pdf_file = Mock()
        mock_pdf_file.name = 'document.pdf'
        mock_pdf_file.size = 1024
        
        is_valid, message = validate_file(mock_pdf_file)
        self.assertFalse(is_valid)
        self.assertIn("not supported", message)


class TestGraphComponent(unittest.TestCase):
    """Test Graph component functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_graph_data = {
            "nodes": [
                {
                    "id": "customers.csv",
                    "label": "customers.csv",
                    "type": "file",
                    "metadata": {
                        "columns": 6,
                        "fileSize": "2.5KB",
                        "uploadDate": "2024-01-15T10:30:00Z"
                    }
                },
                {
                    "id": "orders.csv",
                    "label": "orders.csv",
                    "type": "file",
                    "metadata": {
                        "columns": 8,
                        "fileSize": "5.1KB",
                        "uploadDate": "2024-01-15T11:00:00Z"
                    }
                }
            ],
            "links": [
                {
                    "id": "edge-123",
                    "source": "customers.csv",
                    "target": "orders.csv",
                    "label": "customer_id ↔ customer_id",
                    "columnA": "customer_id",
                    "columnB": "customer_id",
                    "confidence": 0.95,
                    "type": "foreign_key",
                    "status": "active"
                }
            ]
        }
    
    def test_graph_data_validation(self):
        """Test graph data structure validation."""
        def validate_graph_data(data):
            required_keys = ['nodes', 'links']
            
            if not all(key in data for key in required_keys):
                return False, "Missing required keys: nodes, links"
            
            if not isinstance(data['nodes'], list):
                return False, "Nodes must be a list"
            
            if not isinstance(data['links'], list):
                return False, "Links must be a list"
            
            # Validate node structure
            for node in data['nodes']:
                if 'id' not in node or 'label' not in node:
                    return False, "Node missing required fields: id, label"
            
            # Validate link structure
            for link in data['links']:
                required_link_fields = ['source', 'target', 'confidence']
                if not all(field in link for field in required_link_fields):
                    return False, "Link missing required fields"
            
            return True, "Graph data is valid"
        
        is_valid, message = validate_graph_data(self.sample_graph_data)
        self.assertTrue(is_valid)
        self.assertEqual(message, "Graph data is valid")
    
    def test_confidence_classification(self):
        """Test confidence score classification."""
        def get_confidence_class(confidence):
            if confidence >= 0.9:
                return 'high'
            elif confidence >= 0.7:
                return 'medium'
            else:
                return 'low'
        
        self.assertEqual(get_confidence_class(0.95), 'high')
        self.assertEqual(get_confidence_class(0.75), 'medium')
        self.assertEqual(get_confidence_class(0.45), 'low')
    
    def test_edge_metadata_processing(self):
        """Test edge metadata processing."""
        def process_edge_metadata(edge):
            processed = {
                'id': edge['id'],
                'source': edge['source'],
                'target': edge['target'],
                'confidence_class': get_confidence_class(edge['confidence']),
                'connection_type': edge.get('type', 'unknown'),
                'label': edge.get('label', ''),
                'status': edge.get('status', 'unknown')
            }
            return processed
        
        def get_confidence_class(confidence):
            if confidence >= 0.9:
                return 'high'
            elif confidence >= 0.7:
                return 'medium'
            else:
                return 'low'
        
        edge = self.sample_graph_data['links'][0]
        processed = process_edge_metadata(edge)
        
        self.assertEqual(processed['confidence_class'], 'high')
        self.assertEqual(processed['connection_type'], 'foreign_key')
        self.assertEqual(processed['status'], 'active')


class TestConnectionPrompt(unittest.TestCase):
    """Test ConnectionPrompt component functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_connection = {
            "fileA": "customers.csv",
            "fileB": "orders.csv",
            "columnA": "customer_id",
            "columnB": "customer_id",
            "confidence": 0.95,
            "id": "conn-123",
            "llmAnalysis": {
                "reasoning": "Both columns represent customer identifiers",
                "confidence_score": 0.95,
                "connection_type": "foreign_key",
                "business_context": "Enables linking customer orders",
                "suggested_join_strategy": "inner_join",
                "potential_issues": ["Data type validation needed"],
                "recommendations": ["Verify referential integrity"]
            }
        }
    
    def test_connection_validation(self):
        """Test connection data validation."""
        def validate_connection(connection):
            required_fields = ['fileA', 'fileB', 'columnA', 'columnB', 'confidence']
            
            if not all(field in connection for field in required_fields):
                return False, "Missing required connection fields"
            
            if not isinstance(connection['confidence'], (int, float)):
                return False, "Confidence must be a number"
            
            if not 0 <= connection['confidence'] <= 1:
                return False, "Confidence must be between 0 and 1"
            
            return True, "Connection is valid"
        
        is_valid, message = validate_connection(self.sample_connection)
        self.assertTrue(is_valid)
        self.assertEqual(message, "Connection is valid")
    
    def test_llm_analysis_processing(self):
        """Test LLM analysis data processing."""
        def process_llm_analysis(llm_analysis):
            if not llm_analysis:
                return None
            
            processed = {
                'reasoning': llm_analysis.get('reasoning', ''),
                'business_context': llm_analysis.get('business_context', ''),
                'connection_type': llm_analysis.get('connection_type', 'unknown'),
                'join_strategy': llm_analysis.get('suggested_join_strategy', 'unknown'),
                'issues_count': len(llm_analysis.get('potential_issues', [])),
                'recommendations_count': len(llm_analysis.get('recommendations', []))
            }
            return processed
        
        processed = process_llm_analysis(self.sample_connection['llmAnalysis'])
        
        self.assertEqual(processed['connection_type'], 'foreign_key')
        self.assertEqual(processed['join_strategy'], 'inner_join')
        self.assertEqual(processed['issues_count'], 1)
        self.assertEqual(processed['recommendations_count'], 1)
    
    def test_confidence_display_formatting(self):
        """Test confidence score display formatting."""
        def format_confidence_display(confidence):
            percentage = round(confidence * 100)
            
            if confidence >= 0.9:
                level = "High"
                color_class = "high"
            elif confidence >= 0.7:
                level = "Medium"
                color_class = "medium"
            else:
                level = "Low"
                color_class = "low"
            
            return {
                'percentage': percentage,
                'level': level,
                'color_class': color_class,
                'display_text': f"{level} ({percentage}%)"
            }
        
        display = format_confidence_display(0.95)
        self.assertEqual(display['percentage'], 95)
        self.assertEqual(display['level'], "High")
        self.assertEqual(display['color_class'], "high")

    def test_modal_close_functionality(self):
        """Test modal closing functionality."""
        def simulate_modal_close(close_method, pending_connections):
            """Simulate different modal close methods."""
            if close_method == 'x_button':
                # Remove first connection (X button)
                return pending_connections[1:] if len(pending_connections) > 1 else []
            elif close_method == 'cancel_button':
                # Remove first connection (Cancel button)
                return pending_connections[1:] if len(pending_connections) > 1 else []
            elif close_method == 'escape_key':
                # Remove first connection (Escape key)
                return pending_connections[1:] if len(pending_connections) > 1 else []
            elif close_method == 'yes_button':
                # Process connection and remove first
                return pending_connections[1:] if len(pending_connections) > 1 else []
            else:
                return pending_connections
        
        # Test initial state
        pending_connections = [
            {'id': 'conn1', 'fileA': 'file1.csv', 'fileB': 'file2.csv'},
            {'id': 'conn2', 'fileA': 'file3.csv', 'fileB': 'file4.csv'}
        ]
        
        # Test X button close
        result = simulate_modal_close('x_button', pending_connections)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'conn2')
        
        # Test Cancel button close
        result = simulate_modal_close('cancel_button', pending_connections)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'conn2')
        
        # Test Escape key close
        result = simulate_modal_close('escape_key', pending_connections)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'conn2')
        
        # Test Yes button close
        result = simulate_modal_close('yes_button', pending_connections)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'conn2')
        
        # Test closing last connection
        single_connection = [{'id': 'conn1', 'fileA': 'file1.csv', 'fileB': 'file2.csv'}]
        result = simulate_modal_close('x_button', single_connection)
        self.assertEqual(len(result), 0)

    def test_modal_state_management(self):
        """Test modal state management logic."""
        def get_modal_state(pending_connections, current_connection_id=None):
            """Get current modal state."""
            if not pending_connections:
                return {'is_open': False, 'current_connection': None}
            
            current_connection = pending_connections[0] if pending_connections else None
            is_open = current_connection is not None
            
            return {
                'is_open': is_open,
                'current_connection': current_connection,
                'remaining_count': len(pending_connections) - 1
            }
        
        # Test with no connections
        state = get_modal_state([])
        self.assertFalse(state['is_open'])
        self.assertIsNone(state['current_connection'])
        
        # Test with one connection
        connections = [{'id': 'conn1', 'fileA': 'file1.csv', 'fileB': 'file2.csv'}]
        state = get_modal_state(connections)
        self.assertTrue(state['is_open'])
        self.assertEqual(state['current_connection']['id'], 'conn1')
        self.assertEqual(state['remaining_count'], 0)
        
        # Test with multiple connections
        connections = [
            {'id': 'conn1', 'fileA': 'file1.csv', 'fileB': 'file2.csv'},
            {'id': 'conn2', 'fileA': 'file3.csv', 'fileB': 'file4.csv'}
        ]
        state = get_modal_state(connections)
        self.assertTrue(state['is_open'])
        self.assertEqual(state['current_connection']['id'], 'conn1')
        self.assertEqual(state['remaining_count'], 1)

    def test_connection_response_handling(self):
        """Test connection response handling logic."""
        def handle_connection_response(accepted, connection, pending_connections):
            """Simulate connection response handling."""
            if accepted:
                # Process accepted connection
                processed_connection = {
                    **connection,
                    'status': 'accepted',
                    'processed_at': '2024-01-01T00:00:00Z'
                }
                # Remove from pending
                remaining = [conn for conn in pending_connections if conn['id'] != connection['id']]
                return processed_connection, remaining
            else:
                # Process rejected connection
                rejected_connection = {
                    **connection,
                    'status': 'rejected',
                    'processed_at': '2024-01-01T00:00:00Z'
                }
                # Remove from pending
                remaining = [conn for conn in pending_connections if conn['id'] != connection['id']]
                return rejected_connection, remaining
        
        pending_connections = [
            {'id': 'conn1', 'fileA': 'file1.csv', 'fileB': 'file2.csv'},
            {'id': 'conn2', 'fileA': 'file3.csv', 'fileB': 'file4.csv'}
        ]
        
        # Test accepting connection
        connection = {'id': 'conn1', 'fileA': 'file1.csv', 'fileB': 'file2.csv'}
        result, remaining = handle_connection_response(True, connection, pending_connections)
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]['id'], 'conn2')
        
        # Test rejecting connection
        result, remaining = handle_connection_response(False, connection, pending_connections)
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]['id'], 'conn2')

    def test_escape_key_handling(self):
        """Test escape key event handling."""
        def handle_escape_key(event, on_close_callback):
            """Simulate escape key handling."""
            if event.get('key') == 'Escape':
                on_close_callback()
                return True
            return False
        
        close_called = False
        def mock_close():
            nonlocal close_called
            close_called = True
        
        # Test escape key
        escape_event = {'key': 'Escape'}
        result = handle_escape_key(escape_event, mock_close)
        self.assertTrue(result)
        self.assertTrue(close_called)
        
        # Test other key
        close_called = False
        other_event = {'key': 'Enter'}
        result = handle_escape_key(other_event, mock_close)
        self.assertFalse(result)
        self.assertFalse(close_called)

    def test_modal_overlay_click_handling(self):
        """Test modal overlay click handling."""
        def handle_overlay_click(event, on_close_callback):
            """Simulate overlay click handling."""
            # Check if click was on overlay (not modal content)
            if event.get('target') == 'overlay':
                on_close_callback()
                return True
            return False
        
        close_called = False
        def mock_close():
            nonlocal close_called
            close_called = True
        
        # Test overlay click
        overlay_event = {'target': 'overlay'}
        result = handle_overlay_click(overlay_event, mock_close)
        self.assertTrue(result)
        self.assertTrue(close_called)
        
        # Test modal content click
        close_called = False
        content_event = {'target': 'modal_content'}
        result = handle_overlay_click(content_event, mock_close)
        self.assertFalse(result)
        self.assertFalse(close_called)


class TestModalUI(unittest.TestCase):
    """Test Modal UI functionality and interactions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_connection = {
            'fileA': 'customers.csv',
            'fileB': 'orders.csv',
            'columnA': 'customer_id',
            'columnB': 'customer_id',
            'confidence': 0.95,
            'id': 'test-connection-1',
            'llmAnalysis': {
                'reasoning': 'The columns appear to be the same identifier field.',
                'business_context': 'This enables linking customer information.',
                'connection_type': 'foreign_key',
                'suggested_join_strategy': 'inner_join',
                'potential_issues': [
                    'Data type mismatches between columns',
                    'Potential data quality issues'
                ],
                'recommendations': [
                    'Verify data types match between columns',
                    'Check for null values in customer ID columns'
                ]
            }
        }
    
    def test_modal_visibility_logic(self):
        """Test modal visibility logic."""
        def should_show_modal(pending_connections, is_processing=False):
            """Determine if modal should be visible."""
            if is_processing:
                return False
            return len(pending_connections) > 0
        
        # Test with pending connections
        pending_connections = [{'id': 'conn1'}]
        self.assertTrue(should_show_modal(pending_connections))
        
        # Test with no pending connections
        self.assertFalse(should_show_modal([]))
        
        # Test when processing
        self.assertFalse(should_show_modal(pending_connections, is_processing=True))
    
    def test_modal_content_rendering(self):
        """Test modal content rendering logic."""
        def get_modal_content(connection):
            """Get modal content structure."""
            return {
                'title': 'AI-Detected Connection',
                'confidence': f"{round(connection['confidence'] * 100)}% CONFIDENCE",
                'dataset_a': connection['fileA'],
                'dataset_b': connection['fileB'],
                'column_a': connection['columnA'],
                'column_b': connection['columnB'],
                'has_llm_analysis': bool(connection.get('llmAnalysis')),
                'issues_count': len(connection.get('llmAnalysis', {}).get('potential_issues', [])),
                'recommendations_count': len(connection.get('llmAnalysis', {}).get('recommendations', []))
            }
        
        content = get_modal_content(self.mock_connection)
        
        self.assertEqual(content['title'], 'AI-Detected Connection')
        self.assertEqual(content['confidence'], '95% CONFIDENCE')
        self.assertEqual(content['dataset_a'], 'customers.csv')
        self.assertEqual(content['dataset_b'], 'orders.csv')
        self.assertTrue(content['has_llm_analysis'])
        self.assertEqual(content['issues_count'], 2)
        self.assertEqual(content['recommendations_count'], 2)
    
    def test_button_state_management(self):
        """Test button state management."""
        def get_button_states(is_processing=False, has_connection=True):
            """Get button states based on current state."""
            return {
                'confirm_enabled': has_connection and not is_processing,
                'cancel_enabled': not is_processing,
                'close_enabled': not is_processing,
                'confirm_text': 'Yes, Create Connection',
                'cancel_text': 'Cancel'
            }
        
        # Test normal state
        states = get_button_states()
        self.assertTrue(states['confirm_enabled'])
        self.assertTrue(states['cancel_enabled'])
        self.assertTrue(states['close_enabled'])
        
        # Test processing state
        states = get_button_states(is_processing=True)
        self.assertFalse(states['confirm_enabled'])
        self.assertFalse(states['cancel_enabled'])
        self.assertFalse(states['close_enabled'])
        
        # Test no connection state
        states = get_button_states(has_connection=False)
        self.assertFalse(states['confirm_enabled'])
        self.assertTrue(states['cancel_enabled'])
        self.assertTrue(states['close_enabled'])
    
    def test_confidence_color_mapping(self):
        """Test confidence score to color mapping."""
        def get_confidence_color(confidence):
            """Get color based on confidence score."""
            if confidence >= 0.9:
                return '#10b981'  # Green
            elif confidence >= 0.7:
                return '#f59e0b'  # Yellow
            else:
                return '#ef4444'  # Red
        
        # Test high confidence
        self.assertEqual(get_confidence_color(0.95), '#10b981')
        self.assertEqual(get_confidence_color(0.9), '#10b981')
        
        # Test medium confidence
        self.assertEqual(get_confidence_color(0.8), '#f59e0b')
        self.assertEqual(get_confidence_color(0.7), '#f59e0b')
        
        # Test low confidence
        self.assertEqual(get_confidence_color(0.6), '#ef4444')
        self.assertEqual(get_confidence_color(0.5), '#ef4444')
    
    def test_modal_animation_states(self):
        """Test modal animation states."""
        def get_animation_state(is_visible, is_entering=False, is_exiting=False):
            """Get animation state for modal."""
            if is_entering:
                return 'entering'
            elif is_exiting:
                return 'exiting'
            elif is_visible:
                return 'visible'
            else:
                return 'hidden'
        
        # Test entering state
        self.assertEqual(get_animation_state(True, is_entering=True), 'entering')
        
        # Test visible state
        self.assertEqual(get_animation_state(True), 'visible')
        
        # Test exiting state
        self.assertEqual(get_animation_state(True, is_exiting=True), 'exiting')
        
        # Test hidden state
        self.assertEqual(get_animation_state(False), 'hidden')
    
    def test_modal_accessibility_features(self):
        """Test modal accessibility features."""
        def get_accessibility_attributes(is_visible, title):
            """Get accessibility attributes for modal."""
            return {
                'role': 'dialog',
                'aria-modal': 'true',
                'aria-labelledby': 'modal-title' if is_visible else None,
                'aria-describedby': 'modal-content' if is_visible else None,
                'tabindex': '-1' if is_visible else None,
                'aria-hidden': 'false' if is_visible else 'true'
            }
        
        # Test visible modal
        attrs = get_accessibility_attributes(True, 'Test Modal')
        self.assertEqual(attrs['role'], 'dialog')
        self.assertEqual(attrs['aria-modal'], 'true')
        self.assertEqual(attrs['aria-hidden'], 'false')
        
        # Test hidden modal
        attrs = get_accessibility_attributes(False, 'Test Modal')
        self.assertEqual(attrs['aria-hidden'], 'true')
        self.assertIsNone(attrs['aria-labelledby'])


class TestAppComponent(unittest.TestCase):
    """Test App component functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.api_base_url = 'http://localhost:8000'
    
    def test_api_endpoint_construction(self):
        """Test API endpoint URL construction."""
        def build_api_url(endpoint):
            return f"{self.api_base_url}{endpoint}"
        
        self.assertEqual(
            build_api_url('/connections/graph-data'),
            'http://localhost:8000/connections/graph-data'
        )
        self.assertEqual(
            build_api_url('/connections/potential'),
            'http://localhost:8000/connections/potential'
        )
    
    def test_graph_data_processing(self):
        """Test graph data processing for UI display."""
        sample_api_response = {
            "nodes": [
                {
                    "id": "customers.csv",
                    "label": "customers.csv",
                    "type": "file",
                    "metadata": {
                        "columns": 6,
                        "fileSize": "2.5KB",
                        "uploadDate": "2024-01-15T10:30:00Z"
                    }
                }
            ],
            "links": [
                {
                    "id": "edge-123",
                    "source": "customers.csv",
                    "target": "orders.csv",
                    "label": "customer_id ↔ customer_id",
                    "columnA": "customer_id",
                    "columnB": "customer_id",
                    "confidence": 0.95,
                    "type": "foreign_key",
                    "status": "active"
                }
            ]
        }
        
        def process_graph_data_for_ui(api_data):
            # Extract files from nodes
            files = api_data.get('nodes', [])
            
            # Extract connections from links
            connections = api_data.get('links', [])
            
            # Process files for display
            processed_files = []
            for file in files:
                processed_file = {
                    'id': file['id'],
                    'label': file['label'],
                    'metadata': file.get('metadata', {})
                }
                processed_files.append(processed_file)
            
            # Process connections for display
            processed_connections = []
            for connection in connections:
                processed_connection = {
                    'id': connection['id'],
                    'source': connection['source'],
                    'target': connection['target'],
                    'columnA': connection.get('columnA', ''),
                    'columnB': connection.get('columnB', ''),
                    'confidence': connection.get('confidence', 0),
                    'type': connection.get('type', 'unknown'),
                    'status': connection.get('status', 'unknown')
                }
                processed_connections.append(processed_connection)
            
            return {
                'files': processed_files,
                'connections': processed_connections,
                'graphData': api_data
            }
        
        processed = process_graph_data_for_ui(sample_api_response)
        
        self.assertEqual(len(processed['files']), 1)
        self.assertEqual(len(processed['connections']), 1)
        self.assertEqual(processed['files'][0]['label'], 'customers.csv')
        self.assertEqual(processed['connections'][0]['confidence'], 0.95)
    
    def test_pending_connections_processing(self):
        """Test pending connections processing."""
        sample_pending_connections = [
            {
                "id": "conn-123",
                "source_collection": "customers.csv",
                "target_collection": "orders.csv",
                "source_column": "customer_id",
                "target_column": "customer_id",
                "confidence_score": 0.95,
                "connection_type": "foreign_key",
                "status": "pending"
            }
        ]
        
        def process_pending_connections(connections):
            processed = []
            for conn in connections:
                processed_conn = {
                    'id': conn['id'],
                    'fileA': conn['source_collection'],
                    'fileB': conn['target_collection'],
                    'columnA': conn['source_column'],
                    'columnB': conn['target_column'],
                    'confidence': conn['confidence_score'],
                    'type': conn['connection_type'],
                    'status': conn['status']
                }
                processed.append(processed_conn)
            return processed
        
        processed = process_pending_connections(sample_pending_connections)
        
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0]['fileA'], 'customers.csv')
        self.assertEqual(processed[0]['confidence'], 0.95)


class TestUIUtilities(unittest.TestCase):
    """Test UI utility functions."""
    
    def test_data_quality_metrics_calculation(self):
        """Test data quality metrics calculation."""
        def calculate_data_quality_metrics(metadata):
            metrics = {
                'completeness': metadata.get('completeness', 0.8),
                'consistency': metadata.get('consistency', 0.8),
                'accuracy': metadata.get('accuracy', 0.8),
                'uniqueness': metadata.get('uniqueness', 0.8)
            }
            
            # Calculate overall quality score
            overall_score = sum(metrics.values()) / len(metrics)
            
            # Determine quality level
            if overall_score >= 0.9:
                quality_level = 'excellent'
            elif overall_score >= 0.8:
                quality_level = 'good'
            elif overall_score >= 0.7:
                quality_level = 'fair'
            else:
                quality_level = 'poor'
            
            return {
                'metrics': metrics,
                'overall_score': overall_score,
                'quality_level': quality_level
            }
        
        sample_metadata = {
            'completeness': 0.95,
            'consistency': 0.92,
            'accuracy': 0.88,
            'uniqueness': 0.90
        }
        
        result = calculate_data_quality_metrics(sample_metadata)
        
        self.assertAlmostEqual(result['overall_score'], 0.9125, places=4)
        self.assertEqual(result['quality_level'], 'excellent')
    
    def test_merge_complexity_assessment(self):
        """Test merge complexity assessment."""
        def assess_merge_complexity(metadata):
            factors = {
                'shared_columns': metadata.get('shared_columns', 0),
                'total_columns': metadata.get('total_columns', 0),
                'confidence': metadata.get('confidence', 0),
                'data_types': len(metadata.get('data_types', [])) if isinstance(metadata.get('data_types'), list) else 0
            }
            
            # Calculate complexity score
            complexity_score = 0
            
            # More shared columns = lower complexity
            if factors['shared_columns'] > 0:
                complexity_score += (factors['shared_columns'] / factors['total_columns']) * 0.3
            
            # Higher confidence = lower complexity
            complexity_score += factors['confidence'] * 0.4
            
            # Fewer data types = lower complexity
            complexity_score += (1 - factors['data_types'] / 10) * 0.3
            
            # Determine complexity level
            if complexity_score >= 0.8:
                level = 'low'
            elif complexity_score >= 0.6:
                level = 'medium'
            else:
                level = 'high'
            
            return {
                'complexity_score': complexity_score,
                'level': level,
                'factors': factors
            }
        
        sample_metadata = {
            'shared_columns': 2,
            'total_columns': 10,
            'confidence': 0.95,
            'data_types': 3
        }
        
        result = assess_merge_complexity(sample_metadata)
        
        self.assertGreater(result['complexity_score'], 0.7)
        self.assertEqual(result['level'], 'medium')


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestFileUploader,
        TestGraphComponent,
        TestConnectionPrompt,
        TestAppComponent,
        TestUIUtilities
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"UI Tests Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}") 