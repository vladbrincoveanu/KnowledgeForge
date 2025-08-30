import React from 'react';
import { useState, useCallback, useEffect } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  useLocation,
} from 'react-router-dom';
import { wsService } from './services/api';
import FileUploader from './components/FileUploader';
import Graph from './components/Graph';
import ConnectionPrompt from './components/ConnectionPrompt';
import OntologyResults from './components/OntologyResults';
import SystemMetrics from './components/SystemMetrics';
import {
  Database,
  Activity,
  Upload,
  BarChart3,
  Settings,
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
      icon: <Settings size={20} />,
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

  const handleWebSocketMessage = useCallback((data: WebSocketMessage) => {
    if (data.task_id && extractionTasks[data.task_id]) {
      setExtractionTasks(prev => ({
        ...prev,
        [data.task_id!]: {
          ...prev[data.task_id!],
          status:
            (data.status as ExtractionTask['status']) ||
            prev[data.task_id!].status,
          message: data.message || prev[data.task_id!].message,
          timestamp: data.timestamp,
        },
      }));

      // Update graph data when extraction completes
      if (data.status === 'completed') {
        loadGraphData(data.task_id);
      }
    }
  }, [extractionTasks, loadGraphData]);

  useEffect(() => {
    wsService.connect();

    wsService.on('message', handleWebSocketMessage);
    wsService.on('connected', () => console.log('WebSocket connected'));
    wsService.on('disconnected', () => console.log('WebSocket disconnected'));

    return () => {
      wsService.disconnect();
    };
  }, [handleWebSocketMessage]);

  const calculateSimilarity = useCallback((str1: string, str2: string): number => {
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
  }, []);

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

  const loadGraphData = useCallback(async (taskId: string) => {
    try {
      // const graphDataResponse = await ontologyAPI.getGraphVisualization(taskId);

      // Convert Cypher queries to graph data
      const nodes: GraphNode[] = [];
      const links: GraphLink[] = [];

      // This is a simplified conversion - in production you'd parse the Cypher queries
      // For now, we'll create basic graph data from entities and relationships
      if (extractionTasks[taskId]?.results) {
        const { entities, relationships } = extractionTasks[taskId].results!;

        entities.forEach(entity => {
          nodes.push({
            id: entity.id,
            label: entity.name,
            type: 'entity',
            entityType: entity.entity_type,
            confidence: entity.confidence,
          });
        });

        relationships.forEach(rel => {
          links.push({
            id: rel.id,
            source: rel.source_entity_id,
            target: rel.target_entity_id,
            label: rel.relationship_type,
            confidence: rel.confidence,
          });
        });
      }

      setGraphData({ nodes, links });
    } catch (error) {
      console.error('Failed to load graph data:', error);
    }
  }, [extractionTasks]);

  const handleFeedbackSubmitted = useCallback((feedback: any) => {
    console.log('Feedback submitted:', feedback);
    // You can add additional logic here, such as updating the UI
  }, []);

  // Update graph data when active task changes
  useEffect(() => {
    if (activeTaskId && extractionTasks[activeTaskId]?.status === 'completed') {
      loadGraphData(activeTaskId);
    }
  }, [activeTaskId, extractionTasks, loadGraphData]);

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
                  </div>

                  <Graph data={graphData} />
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
                      <Settings size={32} /> Settings
                    </h1>
                    <p>Configure API settings and application preferences</p>
                  </div>

                  <div className="settings-content">
                    <div className="setting-group">
                      <h3>API Configuration</h3>
                      <div className="setting-item">
                        <label>API Base URL:</label>
                        <input
                          type="text"
                          defaultValue={
                            import.meta.env.VITE_API_URL ||
                            'http://localhost:8000'
                          }
                          placeholder="API base URL"
                        />
                      </div>
                      <div className="setting-item">
                        <label>API Key:</label>
                        <input
                          type="password"
                          defaultValue={
                            import.meta.env.VITE_API_KEY || 'test-api-key-12345'
                          }
                          placeholder="API key"
                        />
                      </div>
                    </div>

                    <div className="setting-group">
                      <h3>Extraction Settings</h3>
                      <div className="setting-item">
                        <label>Default Confidence Threshold:</label>
                        <input
                          type="range"
                          min="0.1"
                          max="1.0"
                          step="0.1"
                          defaultValue="0.7"
                        />
                        <span>0.7</span>
                      </div>
                      <div className="setting-item">
                        <label>Auto-refresh Metrics:</label>
                        <input type="checkbox" defaultChecked />
                      </div>
                    </div>

                    <button className="btn-save-settings">Save Settings</button>
                  </div>
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
