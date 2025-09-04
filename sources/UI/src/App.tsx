import React from 'react';
import { useState, useCallback, useEffect } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  useLocation,
} from 'react-router-dom';
import { wsService, ontologyAPI } from './services/api';
import FileUploader from './@components/upload-extract/FileUploader/FileUploader';
import Graph from './@components/graph-view/Graph/Graph';
import ConnectionPrompt from './@components/upload-extract/ConnectionPrompt/ConnectionPrompt';
import OntologyResults from './@components/ontology-results/OntologyResults/OntologyResults';
import SystemMetrics from './@components/system-metrics/SystemMetrics/SystemMetrics';
import Settings from './@components/settings/Settings/Settings';
import {
  Database,
  Activity,
  Upload,
  BarChart3,
  Settings as SettingsIcon,
  Brain,
} from 'lucide-react';
import './App.scss';

// TypeScript interfaces
interface NavItem {
  id: string;
  label: string;
  icon: React.ReactElement;
  path: string;
}

interface UploadedFile {
  name: string;
  headers: string[];
  data: Record<string, string>[];
  size: number;
  rowCount: number;
  type: string;
}

interface Connection {
  columnA: string;
  columnB: string;
  confidence: number;
}

interface PotentialConnection {
  fileA: string;
  fileB: string;
  columnA: string;
  columnB: string;
  confidence: number;
}

interface ExtractionTask {
  taskId: string;
  fileName: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  message: string;
  createdAt: string;
  timestamp?: string;
  results?: {
    entities: Entity[];
    relationships: Relationship[];
  };
}

interface Entity {
  id: string;
  name: string;
  entity_type: string;
  confidence: number;
}

interface Relationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: string;
  confidence: number;
}

interface GraphNode {
  id: string;
  label: string;
  type: string;
  entityType?: string;
  confidence?: number;
}

interface GraphLink {
  id: string;
  source: string;
  target: string;
  label: string;
  confidence?: number;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface FileHeader {
  name: string;
  headers: string[];
}

interface WebSocketMessage {
  task_id?: string;
  status?: string;
  message?: string;
  timestamp?: string;
}

interface NavigationProps {
  activeTab: string;
}

// Navigation component
const Navigation: React.FC<NavigationProps> = ({ activeTab }) => {
  const navItems: NavItem[] = [
    {
      id: 'upload',
      label: 'Upload & Extract',
      icon: <Upload size={20} />,
      path: '/',
    },
    {
      id: 'results',
      label: 'Ontology Results',
      icon: <Database size={20} />,
      path: '/results',
    },
    {
      id: 'graph',
      label: 'Graph View',
      icon: <BarChart3 size={20} />,
      path: '/graph',
    },
    {
      id: 'metrics',
      label: 'System Metrics',
      icon: <Activity size={20} />,
      path: '/metrics',
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: <SettingsIcon size={20} />,
      path: '/settings',
    },
  ];

  return (
    <nav className="main-navigation">
      <div className="nav-header">
        <Brain size={24} />
        <h2>KnowledgeForge</h2>
      </div>
      <ul className="nav-list">
        {navItems.map(item => (
          <li key={item.id}>
            <Link
              to={item.path}
              className={`nav-link ${activeTab === item.id ? 'active' : ''}`}
            >
              {item.icon}
              <span>{item.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
};

// Main content wrapper
const MainContent: React.FC = () => {
  const location = useLocation();
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [connections, setConnections] = useState<PotentialConnection[]>([]);
  const [pendingConnection, setPendingConnection] =
    useState<PotentialConnection | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [extractionTasks, setExtractionTasks] = useState<
    Record<string, ExtractionTask>
  >({});
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<GraphData>({
    nodes: [],
    links: [],
  });

  const loadGraphData = useCallback(
    async (taskId: string) => {
      try {
        console.log('Loading graph data for task:', taskId);
        
        // First try to get graph data from the dedicated graph API endpoint
        try {
          const graphDataResponse = await ontologyAPI.getGraphVisualization(taskId);
          console.log('Graph data from API:', graphDataResponse);
          
          // Convert API response to our GraphData format
          const nodes: GraphNode[] = graphDataResponse.nodes.map((node: any) => ({
            id: node.id,
            label: node.label,
            type: node.type,
            entityType: node.properties?.entityType || node.type,
            confidence: node.properties?.confidence || 1.0,
          }));
          
          const links: GraphLink[] = graphDataResponse.edges.map((edge: any) => ({
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: edge.type,
            confidence: edge.properties?.confidence || 1.0,
          }));
          
          setGraphData({ nodes, links });
          return;
        } catch (apiError) {
          console.log('Graph API not available, loading from entities and relationships:', apiError);
        }

        // Fallback: Load entities and relationships directly from API (same as Ontology Results)
        console.log('Loading entities and relationships from API...');
        
        // Load entities and relationships the same way as Ontology Results
        const entitiesData = await ontologyAPI.getEntities(taskId, 100, 0);
        const relationshipsData = await ontologyAPI.getRelationships(taskId, 100, 0);
        
        const entities = entitiesData.items || [];
        const relationships = relationshipsData.items || [];
        
        console.log('Loaded entities:', entities.length);
        console.log('Loaded relationships:', relationships.length);
        console.log('Sample entity:', entities[0]);
        console.log('Sample relationship:', relationships[0]);
        console.log('All relationships:', relationships);
        console.log('Entity names:', entities.map(e => e.name));

        // Convert to graph data
        const nodes: GraphNode[] = entities.map(entity => ({
          id: entity.id || `entity-${entity.name}`,
          label: entity.name,
          type: 'entity',
          entityType: entity.entity_type,
          confidence: entity.confidence,
        }));

        // Debug: Log all node IDs
        console.log('Node IDs:', nodes.map(n => n.id));

        const links: GraphLink[] = relationships.map(rel => {
          console.log('Processing relationship:', rel);
          
          // The API returns source_entity and target_entity (names) instead of IDs
          // We need to find the corresponding entity IDs by matching the names
          const sourceEntity = entities.find(entity => entity.name === rel.source_entity);
          const targetEntity = entities.find(entity => entity.name === rel.target_entity);
          
          if (!sourceEntity || !targetEntity) {
            console.warn('Could not find entities for relationship:', rel);
            console.warn('Source entity name:', rel.source_entity, 'Found:', sourceEntity);
            console.warn('Target entity name:', rel.target_entity, 'Found:', targetEntity);
            return null;
          }
          
          const link = {
            id: rel.id || `rel-${sourceEntity.id}-${targetEntity.id}`,
            source: sourceEntity.id || `entity-${sourceEntity.name}`,
            target: targetEntity.id || `entity-${targetEntity.name}`,
            label: rel.relationship_type,
            confidence: rel.confidence,
          };
          console.log('Created link:', link);
          return link;
        }).filter(Boolean) as GraphLink[];

        // Debug: Log all relationship references
        console.log('Relationship source IDs:', links.map(l => l.source));
        console.log('Relationship target IDs:', links.map(l => l.target));
        
        // Check if relationship IDs match entity IDs
        const entityIds = new Set(nodes.map(n => n.id));
        console.log('Available entity IDs:', Array.from(entityIds));
        
        links.forEach(link => {
          if (!entityIds.has(link.source)) {
            console.warn(`Link source ID not found in entities: ${link.source}`);
          }
          if (!entityIds.has(link.target)) {
            console.warn(`Link target ID not found in entities: ${link.target}`);
          }
        });

        // Filter out relationships that reference non-existent nodes
        const validLinks = links.filter(link => {
          const sourceExists = nodes.some(node => node.id === link.source);
          const targetExists = nodes.some(node => node.id === link.target);
          
          if (!sourceExists) {
            console.warn(`Relationship source node not found: ${link.source}`);
          }
          if (!targetExists) {
            console.warn(`Relationship target node not found: ${link.target}`);
          }
          
          return sourceExists && targetExists;
        });

        console.log(`Filtered ${links.length - validLinks.length} invalid relationships`);

        console.log('Final graph data:', { nodes, links: validLinks });
        console.log('Number of valid links:', validLinks.length);
        console.log('Valid links details:', validLinks);
        setGraphData({ nodes, links: validLinks });
      } catch (error) {
        console.error('Failed to load graph data:', error);
        // Set empty graph data on error
        setGraphData({ nodes: [], links: [] });
      }
    },
    []
  );

  const handleWebSocketMessage = useCallback(
    (data?: unknown) => {
      const wsData = data as WebSocketMessage;
      if (wsData?.task_id && extractionTasks[wsData.task_id]) {
        setExtractionTasks(prev => ({
          ...prev,
          [wsData.task_id!]: {
            ...prev[wsData.task_id!],
            status:
              (wsData.status as ExtractionTask['status']) ||
              prev[wsData.task_id!].status,
            message: wsData.message || prev[wsData.task_id!].message,
            timestamp: wsData.timestamp,
          },
        }));
      }
    },
    [extractionTasks]
  );

  useEffect(() => {
    wsService.connect();

    wsService.on('message', handleWebSocketMessage);
    wsService.on('connected', () => console.log('WebSocket connected'));
    wsService.on('disconnected', () => console.log('WebSocket disconnected'));

    return () => {
      wsService.disconnect();
    };
  }, [handleWebSocketMessage]);

  // Effect to load graph data when tasks are completed
  useEffect(() => {
    Object.values(extractionTasks).forEach(task => {
      if (task.status === 'completed') {
        console.log('Task completed, loading graph data:', task.taskId);
        loadGraphData(task.taskId);
      }
    });
  }, [extractionTasks, loadGraphData]);

  const calculateSimilarity = useCallback(
    (str1: string, str2: string): number => {
      const normalize = (str: string) =>
        str.toLowerCase().replace(/[^a-z0-9]/g, '');
      const norm1 = normalize(str1);
      const norm2 = normalize(str2);

      if (norm1 === norm2) return 1.0;
      if (norm1.includes(norm2) || norm2.includes(norm1)) return 0.8;
      if (norm1.includes('id') && norm2.includes('id')) return 0.7;
      if (norm1.includes('name') && norm2.includes('name')) return 0.7;
      if (norm1.includes('customer') && norm2.includes('customer')) return 0.9;
      if (norm1.includes('order') && norm2.includes('order')) return 0.9;

      return 0.0;
    },
    []
  );

  const findPotentialConnections = useCallback(
    (headersA: string[], headersB: string[]): Connection[] => {
      const connections: Connection[] = [];

      headersA.forEach(headerA => {
        headersB.forEach(headerB => {
          const similarity = calculateSimilarity(headerA, headerB);
          if (similarity > 0.6) {
            connections.push({
              columnA: headerA,
              columnB: headerB,
              confidence: similarity,
            });
          }
        });
      });

      return connections;
    },
    [calculateSimilarity]
  );

  const checkSemanticConnections = useCallback(
    async (fileHeaders: FileHeader[]): Promise<PotentialConnection[]> => {
      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 1000));

      const potentialConnections: PotentialConnection[] = [];

      // Simple mock logic to find potential connections
      for (let i = 0; i < fileHeaders.length; i++) {
        for (let j = i + 1; j < fileHeaders.length; j++) {
          const fileA = fileHeaders[i];
          const fileB = fileHeaders[j];

          // Check for common patterns in column names
          const connections = findPotentialConnections(
            fileA.headers,
            fileB.headers
          );

          connections.forEach(connection => {
            potentialConnections.push({
              fileA: fileA.name,
              fileB: fileB.name,
              columnA: connection.columnA,
              columnB: connection.columnB,
              confidence: connection.confidence,
            });
          });
        }
      }

      return potentialConnections;
    },
    [findPotentialConnections]
  );

  const handleFilesUploaded = useCallback(
    async (uploadedFiles: UploadedFile[]) => {
      setFiles(uploadedFiles);
      setIsProcessing(true);

      try {
        // Extract headers from each file
        const fileHeaders: FileHeader[] = uploadedFiles.map(file => ({
          name: file.name,
          headers: file.headers,
        }));

        // Check for semantic connections
        const potentialConnections =
          await checkSemanticConnections(fileHeaders);

        if (potentialConnections.length > 0) {
          setPendingConnection(potentialConnections[0]);
        }
      } catch (error) {
        console.error('Error processing files:', error);
      } finally {
        setIsProcessing(false);
      }
    },
    [checkSemanticConnections]
  );

  const handleExtractionStarted = useCallback(
    (taskId: string, file: UploadedFile) => {
      setExtractionTasks(prev => ({
        ...prev,
        [taskId]: {
          taskId,
          fileName: file.name,
          status: 'pending',
          message: 'Task created and queued',
          createdAt: new Date().toISOString(),
        },
      }));

      // Set as active task if it's the first one
      if (!activeTaskId) {
        setActiveTaskId(taskId);
      }
    },
    [activeTaskId]
  );

  const handleConnectionResponse = useCallback(
    (accepted: boolean, connection: PotentialConnection) => {
      if (accepted) {
        setConnections(prev => [...prev, connection]);
      }

      // Remove the current pending connection
      setPendingConnection(null);

      // Check if there are more pending connections
      // This would be handled by the actual implementation
      // For now, we'll just clear the pending connection
    },
    []
  );

  const handleFeedbackSubmitted = useCallback((feedback: unknown) => {
    console.log('Feedback submitted:', feedback);
    // You can add additional logic here, such as updating the UI
  }, []);

  // Update graph data when active task changes
  useEffect(() => {
    if (activeTaskId && extractionTasks[activeTaskId]?.status === 'completed') {
      console.log('Active task changed, loading graph data:', activeTaskId);
      loadGraphData(activeTaskId);
    }
  }, [activeTaskId, extractionTasks, loadGraphData]);

  // Load graph data when navigating to graph view
  useEffect(() => {
    if (location.pathname === '/graph' && activeTaskId) {
      console.log('Navigated to graph view, loading graph data:', activeTaskId);
      loadGraphData(activeTaskId);
    }
  }, [location.pathname, activeTaskId, loadGraphData]);

  // Determine active tab based on location
  const getActiveTab = (): string => {
    const path = location.pathname;
    if (path === '/') return 'upload';
    if (path === '/results') return 'results';
    if (path === '/graph') return 'graph';
    if (path === '/metrics') return 'metrics';
    if (path === '/settings') return 'settings';
    return 'upload';
  };

  const activeTab = getActiveTab();

  return (
    <div className="app">
      <div className="app-container">
        <Navigation activeTab={activeTab} />

        <main className="main-content">
          <Routes>
            <Route
              path="/"
              element={
                <div className="upload-section">
                  <div className="section-header">
                    <h1>
                      <Upload size={32} /> Upload & Extract Ontology
                    </h1>
                    <p>
                      Upload CSV files and extract semantic ontology using
                      AI-powered analysis
                    </p>
                  </div>

                  <FileUploader
                    onFilesUploaded={handleFilesUploaded}
                    isProcessing={isProcessing}
                    onExtractionStarted={handleExtractionStarted}
                  />

                  {files.length > 0 && (
                    <div className="uploaded-files">
                      <h3>Uploaded Files ({files.length})</h3>
                      <ul>
                        {files.map((file, index) => (
                          <li key={index}>
                            <strong>{file.name}</strong>
                            <br />
                            <small>
                              {file.headers.length} columns, {file.rowCount}{' '}
                              rows
                            </small>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {connections.length > 0 && (
                    <div className="connections">
                      <h3>Connections ({connections.length})</h3>
                      <ul>
                        {connections.map((connection, index) => (
                          <li key={index}>
                            <strong>{connection.fileA}</strong> ↔{' '}
                            <strong>{connection.fileB}</strong>
                            <br />
                            <small>
                              {connection.columnA} ↔ {connection.columnB}
                            </small>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {pendingConnection && (
                    <ConnectionPrompt
                      connection={pendingConnection}
                      onResponse={handleConnectionResponse}
                    />
                  )}
                </div>
              }
            />

            <Route
              path="/results"
              element={
                <div className="results-section">
                  <div className="section-header">
                    <h1>
                      <Database size={32} /> Ontology Results
                    </h1>
                    <p>
                      View extracted entities, relationships, and provide
                      feedback
                    </p>
                  </div>

                  {activeTaskId ? (
                    <OntologyResults
                      taskId={activeTaskId}
                      onFeedbackSubmitted={handleFeedbackSubmitted}
                    />
                  ) : (
                    <div className="no-task-selected">
                      <Database size={48} />
                      <h3>No Active Extraction Task</h3>
                      <p>
                        Upload files and start ontology extraction to see
                        results here.
                      </p>
                    </div>
                  )}
                </div>
              }
            />

            <Route
              path="/graph"
              element={
                <div className="graph-section">
                  <div className="section-header">
                    <h1>
                      <BarChart3 size={32} /> Graph Visualization
                    </h1>
                    <p>
                      Interactive visualization of extracted ontology
                      relationships
                    </p>
                    <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                      {activeTaskId && (
                        <button
                          onClick={() => loadGraphData(activeTaskId)}
                          style={{
                            padding: '8px 16px',
                            backgroundColor: '#007bff',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer'
                          }}
                        >
                          Refresh Graph Data
                        </button>
                      )}
                      <button
                        onClick={() => {
                          // Test with simple hardcoded data
                          const testData: GraphData = {
                            nodes: [
                              { id: '1', label: 'Test Node 1', type: 'entity', entityType: 'Test', confidence: 0.9 },
                              { id: '2', label: 'Test Node 2', type: 'entity', entityType: 'Test', confidence: 0.9 }
                            ],
                            links: [
                              { id: 'test-link', source: '1', target: '2', label: 'Test Link', confidence: 0.9 }
                            ]
                          };
                          console.log('Setting test data:', testData);
                          setGraphData(testData);
                        }}
                        style={{
                          padding: '8px 16px',
                          backgroundColor: '#28a745',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer'
                        }}
                      >
                        Test Simple Graph
                      </button>
                    </div>
                  </div>

                  <Graph
                    data={graphData}
                    onEdgeClick={edge => console.log('Edge clicked:', edge)}
                  />
                </div>
              }
            />

            <Route
              path="/metrics"
              element={
                <div className="metrics-section">
                  <div className="section-header">
                    <h1>
                      <Activity size={32} /> System Metrics
                    </h1>
                    <p>
                      Monitor system performance, health, and extraction metrics
                    </p>
                  </div>

                  <SystemMetrics />
                </div>
              }
            />

            <Route
              path="/settings"
              element={
                <div className="settings-section">
                  <div className="section-header">
                    <h1>
                      <SettingsIcon size={32} /> Settings
                    </h1>
                    <p>Configure API settings and application preferences</p>
                  </div>

                  <Settings />
                </div>
              }
            />
          </Routes>
        </main>
      </div>
    </div>
  );
};

// App wrapper with router
const App: React.FC = () => {
  return (
    <Router>
      <MainContent />
    </Router>
  );
};

export default App;
