import React, { useState, useEffect, useCallback } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  useLocation,
} from 'react-router-dom';
import {
  Activity,
  Upload,
  Settings as SettingsIcon,
  Brain,
  Code,
  ChevronLeft,
  ChevronRight,
  Database,
  BarChart3,
} from 'lucide-react';
import './App.scss';
import OntologyResults from './@components/ontology-results/OntologyResults/OntologyResults';
import Graph from './@components/graph-view/Graph/Graph';
import ArchitectureMap from './@components/architecture-map/ArchitectureMap';
import CodeArchitectureViewer from './@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer';
import Notification from './@components/notification/Notification';
import FileUploader from './@components/upload-extract/FileUploader/FileUploader';
import SystemMetrics from './@components/system-metrics/SystemMetrics/SystemMetrics';
import Settings from './@components/settings/Settings/Settings';
import { ontologyAPI, wsService } from './services/api';
import { IncrementalSummary } from '@/types';

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

interface WebSocketMessage {
  task_id?: string;
  status?: string;
  message?: string;
  timestamp?: string;
  progress?: number;
  incremental_summary?: IncrementalSummary;
}

interface NavigationProps {
  activeTab: string;
  isCollapsed: boolean;
  onToggle: () => void;
}

interface ExtractionTask {
  taskId: string;
  fileName: string;
  status: string;
  createdAt: string;
}

interface GraphNode {
  id: string;
  label: string;
  type: string;
  entityType?: string;
  confidence?: number;
  metadata?: any;
  columns?: any;
}

interface GraphLink {
  id: string;
  source: string;
  target: string;
  label: string;
  confidence?: number;
}

// Navigation component
const Navigation: React.FC<NavigationProps> = ({
  activeTab,
  isCollapsed,
  onToggle,
}) => {
  const navItems: NavItem[] = [
    {
      id: 'upload',
      label: 'Upload & Extract',
      icon: <Upload size={20} />,
      path: '/',
    },
    {
      id: 'code-architecture',
      label: 'Code Architecture',
      icon: <Code size={20} />,
      path: '/code-architecture',
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
    <nav className={`main-navigation ${isCollapsed ? 'collapsed' : ''}`}>
      <div className="nav-header">
        <div className="nav-header-content">
          {isCollapsed ? (
            <Brain size={24} />
          ) : (
            <>
              <Brain size={24} />
              <h2>KnowledgeForge</h2>
            </>
          )}
        </div>
        <button
          className="nav-toggle"
          onClick={onToggle}
          aria-label={isCollapsed ? 'Show navigation' : 'Hide navigation'}
          style={{
            background: '#007bff',
            color: '#ffffff',
            border: 'none',
            borderRadius: '6px',
            padding: '0.5rem 0.75rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.875rem',
            fontWeight: 600,
            flexShrink: 0,
          }}
        >
          {isCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
          {!isCollapsed && <span>Hide</span>}
        </button>
      </div>
      {!isCollapsed && (
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
      )}
      {isCollapsed && (
        <ul className="nav-list">
          {navItems.map(item => (
            <li key={item.id}>
              <Link
                to={item.path}
                className={`nav-link ${activeTab === item.id ? 'active' : ''}`}
                title={item.label}
              >
                {item.icon}
                <span>{item.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
};

// Main content wrapper

const MainContent: React.FC = () => {
  const location = useLocation();
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const isProcessing = false;
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [notification, setNotification] = useState<{
    message: string;
    type: 'success' | 'error' | 'info';
  } | null>(null);
  const [isNavCollapsed, setIsNavCollapsed] = useState<boolean>(false);
  const [extractionTasks, setExtractionTasks] = useState<Record<string, ExtractionTask>>({});
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({ nodes: [], links: [] });
  const [activeTaskSummary, setActiveTaskSummary] = useState<IncrementalSummary | null>(null);

  const showNotification = (
    message: string,
    type: 'success' | 'error' | 'info'
  ) => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const loadGraphData = useCallback(async (taskId: string) => {
    try {
      // First try to get graph data from the dedicated graph API endpoint
      try {
        const graphDataResponse =
          await ontologyAPI.getGraphVisualization(taskId);

        // Convert API response to our GraphData format
        const nodes: GraphNode[] = graphDataResponse.nodes.map((node: any) => ({
          id: node.id,
          label: node.label,
          type: node.type,
          entityType: node.properties?.entityType || node.type,
          confidence: node.properties?.confidence || 1.0,
          metadata: {
            columns: node.properties?.sourceColumns?.length || 0,
            uploadDate: node.properties?.createdAt || new Date().toISOString(),
            sourceColumns: node.properties?.sourceColumns || [],
            sourceValue: node.properties?.sourceValue,
            sourceFile: node.properties?.sourceFile,
            attributes: node.properties?.attributes || {},
          },
          columns: node.properties?.attributes || {},
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
      } catch {
        // Graph API not available, fall back to entities and relationships
      }

      // Fallback: Load entities and relationships directly from API
      const entitiesData = await ontologyAPI.getEntities(taskId, 100, 0);
      const relationshipsData = await ontologyAPI.getRelationships(
        taskId,
        100,
        0
      );

      const entities = entitiesData.items || [];
      const relationships = relationshipsData.items || [];

      // Convert to graph data
      const nodes: GraphNode[] = entities.map(entity => ({
        id: String(entity.id || `entity-${entity.name}`),
        label: entity.name,
        type: 'entity',
        entityType: entity.entity_type,
        confidence: entity.confidence,
        metadata: {
          columns: entity.source_columns?.length || 0,
          uploadDate: new Date().toISOString(),
          sourceColumns: entity.source_columns || [],
          sourceValue: entity.source_value,
          attributes: entity.attributes || {},
        },
        columns: entity.attributes || {},
      }));

      const links: GraphLink[] = relationships
        .map(rel => {
          // The API returns source_entity and target_entity (names) instead of IDs
          // We need to find the corresponding entity IDs by matching the names
          const sourceEntity = entities.find(
            entity => entity.name === rel.source_entity
          );
          const targetEntity = entities.find(
            entity => entity.name === rel.target_entity
          );

          if (!sourceEntity || !targetEntity) {
            return null;
          }

          return {
            id: rel.id || `rel-${sourceEntity.id}-${targetEntity.id}`,
            source: String(sourceEntity.id || `entity-${sourceEntity.name}`),
            target: String(targetEntity.id || `entity-${targetEntity.name}`),
            label: rel.relationship_type,
            confidence: rel.confidence,
          };
        })
        .filter(Boolean) as GraphLink[];

      // Filter out relationships that reference non-existent nodes
      const validLinks = links.filter(link => {
        const sourceExists = nodes.some(node => node.id === link.source);
        const targetExists = nodes.some(node => node.id === link.target);
        return sourceExists && targetExists;
      });

      setGraphData({ nodes, links: validLinks });
    } catch (error) {
      console.error('Failed to load graph data:', error);
      setGraphData({ nodes: [], links: [] });
    }
  }, []);

  const handleWebSocketMessage = useCallback((data?: unknown) => {
    const wsData = data as WebSocketMessage & {
      progress?: number;
      incremental_summary?: IncrementalSummary;
    };
    if (!wsData?.task_id) {
      return;
    }
    // WebSocket message received - could be used for real-time updates in the future
  }, []);

  const loadAvailableTasks = useCallback(async () => {
    try {
      // Load available tasks from the API
      const response = await fetch(
        'http://localhost:8000/api/v1/extract/tasks'
      );
      if (response.ok) {
        const data = await response.json();
        if (data.tasks && data.tasks.length > 0) {
          // Set the most recent completed task as active
          const completedTasks = data.tasks.filter(
            (t: any) => t.status === 'completed'
          );
          const tasksMap: Record<string, ExtractionTask> = {};
          data.tasks.forEach((t: any) => {
            tasksMap[t.task_id] = {
              taskId: t.task_id,
              fileName: t.file_name || t.filename || 'Unknown',
              status: t.status,
              createdAt: t.created_at,
            };
          });
          setExtractionTasks(tasksMap);
          if (completedTasks.length > 0) {
            const mostRecent = completedTasks.sort(
              (a: any, b: any) =>
                new Date(b.created_at).getTime() -
                new Date(a.created_at).getTime()
            )[0];
            setActiveTaskId(mostRecent.task_id);
            setActiveTaskSummary(mostRecent.incremental_summary || null);
          }
        }
      }
    } catch {
      // Failed to load tasks from API
    }
  }, []);

  useEffect(() => {
    wsService.connect();

    const handleConnected = () => {};
    const handleDisconnected = () => {};

    wsService.on('message', handleWebSocketMessage);
    wsService.on('connected', handleConnected);
    wsService.on('disconnected', handleDisconnected);

    // Load available tasks on component mount
    loadAvailableTasks();

    return () => {
      wsService.off('message', handleWebSocketMessage);
      wsService.off('connected', handleConnected);
      wsService.off('disconnected', handleDisconnected);
      wsService.disconnect();
    };
  }, [handleWebSocketMessage, loadAvailableTasks]);

  // Effect to load graph data when tasks are completed
  useEffect(() => {
    Object.values(extractionTasks).forEach(task => {
      if (task.status === 'completed') {
        loadGraphData(task.taskId);
      }
    });
  }, [extractionTasks, loadGraphData]);

  const handleFilesUploaded = useCallback(
    async (uploadedFiles: UploadedFile[]) => {
      setFiles(uploadedFiles);
    },
    []
  );

  const handleExtractionStarted = useCallback(
    (taskId: string, _file: UploadedFile) => {
      // Set as active task (always use the most recent upload)
      setActiveTaskId(taskId);
    },
    [activeTaskId]
  );

  const handleFeedbackSubmitted = useCallback((_feedback: unknown) => {
    // Additional feedback handling logic can be added here
  }, []);

  // Update graph data when active task changes
  useEffect(() => {
    if (activeTaskId && extractionTasks[activeTaskId]?.status === 'completed') {
      loadGraphData(activeTaskId);
    }
  }, [activeTaskId, extractionTasks, loadGraphData]);

  // Load graph data when navigating to graph view
  useEffect(() => {
    if (location.pathname === '/graph') {
      if (activeTaskId) {
        loadGraphData(activeTaskId);
      } else {
        loadGraphDataWithoutTask();
      }
    }
  }, [location.pathname, activeTaskId, loadGraphData]);

  const loadGraphDataWithoutTask = useCallback(async () => {
    // When there's no active task, show empty graph to avoid confusion
    setGraphData({ nodes: [], links: [] });
  }, []);

  // Determine active tab based on location
  const getActiveTab = (): string => {
    const path = location.pathname;
    if (path === '/') return 'upload';
    if (path === '/code-architecture') return 'code-architecture';
    if (path === '/metrics') return 'metrics';
    if (path === '/settings') return 'settings';
    return 'upload';
  };

  const activeTab = getActiveTab();

  return (
    <div className="app">
      {notification && (
        <Notification
          message={notification.message}
          type={notification.type}
          onClose={() => setNotification(null)}
        />
      )}
      <div className="app-container">
        <Navigation
          activeTab={activeTab}
          isCollapsed={isNavCollapsed}
          onToggle={() => {
            setIsNavCollapsed(!isNavCollapsed);
          }}
        />

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
                    showNotification={showNotification}
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

                    {/* Task Selector */}
                    {Object.keys(extractionTasks).length > 0 && (
                      <div style={{ marginBottom: '16px' }}>
                        <label
                          htmlFor="task-selector"
                          style={{
                            display: 'block',
                            marginBottom: '8px',
                            fontWeight: '500',
                            color: '#495057',
                          }}
                        >
                          Select Upload Session:
                        </label>
                        <select
                          id="task-selector"
                          value={activeTaskId || ''}
                          onChange={e => {
                            const selectedTaskId = e.target.value;
                            setActiveTaskId(selectedTaskId);
                            if (selectedTaskId) {
                              loadGraphData(selectedTaskId);
                            } else {
                              setGraphData({ nodes: [], links: [] });
                            }
                          }}
                          style={{
                            padding: '8px 12px',
                            border: '1px solid #ced4da',
                            borderRadius: '4px',
                            backgroundColor: 'white',
                            minWidth: '300px',
                          }}
                        >
                          <option value="">-- Select a task --</option>
                          {Object.values(extractionTasks)
                            .sort(
                              (a, b) =>
                                new Date(b.createdAt).getTime() -
                                new Date(a.createdAt).getTime()
                            )
                            .map(task => (
                              <option key={task.taskId} value={task.taskId}>
                                {task.fileName} - {task.status} (
                                {new Date(task.createdAt).toLocaleString()})
                              </option>
                            ))}
                        </select>
                      </div>
                    )}

                    {activeTaskId ? (
                      <div>
                        <div
                          style={{
                            marginBottom: '12px',
                            padding: '8px 12px',
                            backgroundColor: '#e7f3ff',
                            border: '1px solid #b3d9ff',
                            borderRadius: '4px',
                            fontSize: '14px',
                          }}
                        >
                          <strong>Current Task:</strong>{' '}
                          {extractionTasks[activeTaskId]?.fileName || 'Unknown'}
                          <span
                            style={{
                              marginLeft: '8px',
                              padding: '2px 6px',
                              backgroundColor:
                                extractionTasks[activeTaskId]?.status ===
                                'completed'
                                  ? '#d4edda'
                                  : '#fff3cd',
                              color:
                                extractionTasks[activeTaskId]?.status ===
                                'completed'
                                  ? '#155724'
                                  : '#856404',
                              borderRadius: '3px',
                              fontSize: '12px',
                            }}
                          >
                            {extractionTasks[activeTaskId]?.status || 'unknown'}
                          </span>
                        </div>
                        {activeTaskSummary && (
                          <div
                            style={{
                              marginBottom: '12px',
                              padding: '8px 12px',
                              backgroundColor: '#f8f9fa',
                              border: '1px solid #dee2e6',
                              borderRadius: '4px',
                              fontSize: '13px',
                            }}
                          >
                            <strong>Incremental Summary:</strong> Entities +
                            {activeTaskSummary.added_entities} · Δ
                            {activeTaskSummary.modified_entities} · -
                            {activeTaskSummary.deleted_entities} | Relationships
                            +{activeTaskSummary.added_relationships} · -
                            {activeTaskSummary.deleted_relationships}
                          </div>
                        )}
                        <button
                          onClick={() => loadGraphData(activeTaskId)}
                          style={{
                            padding: '8px 16px',
                            backgroundColor: '#007bff',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                          }}
                        >
                          Refresh Graph Data
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={async () => {
                          try {
                            const graphDataResponse =
                              await ontologyAPI.getGraphVisualization();
                            const nodes: GraphNode[] =
                              graphDataResponse.nodes.map((node: any) => ({
                                id: node.id,
                                label: node.label,
                                type: node.type,
                                entityType:
                                  node.properties?.entityType || node.type,
                                confidence: node.properties?.confidence || 1.0,
                                metadata: {
                                  columns:
                                    node.properties?.sourceColumns?.length || 0,
                                  uploadDate:
                                    node.properties?.createdAt ||
                                    new Date().toISOString(),
                                  sourceColumns:
                                    node.properties?.sourceColumns || [],
                                  sourceValue: node.properties?.sourceValue,
                                  sourceFile: node.properties?.sourceFile,
                                  attributes: node.properties?.attributes || {},
                                },
                                columns: node.properties?.attributes || {},
                              }));

                            const links: GraphLink[] =
                              graphDataResponse.edges.map((edge: any) => ({
                                id: edge.id,
                                source: edge.source,
                                target: edge.target,
                                label: edge.type,
                                confidence: edge.properties?.confidence || 1.0,
                              }));

                            setGraphData({ nodes, links });
                          } catch {
                            // Failed to load graph data
                          }
                        }}
                        style={{
                          padding: '8px 16px',
                          backgroundColor: '#28a745',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          marginTop: '10px',
                        }}
                      >
                        Load All Data from Database
                      </button>
                    )}
                  </div>

                  <Graph
                    data={graphData}
                    onEdgeClick={undefined}
                    activeTaskId={activeTaskId}
                    onGraphUpdate={() => {
                      if (activeTaskId) {
                        loadGraphData(activeTaskId);
                        showNotification(
                          'Graph updated with the latest data!',
                          'info'
                        );
                      }
                    }}
                  />
                </div>
              }
            />

            <Route path="/architecture" element={<ArchitectureMap />} />

            <Route
              path="/code-architecture"
              element={<CodeArchitectureViewer />}
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
