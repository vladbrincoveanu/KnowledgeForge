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
import OntologyResults from './@components/ontology-results/OntologyResults/OntologyResults';
import SystemMetrics from './@components/system-metrics/SystemMetrics/SystemMetrics';
import Settings from './@components/settings/Settings/Settings';
import ArchitectureMap from './@components/architecture-map/ArchitectureMap';
import CodeArchitectureViewer from './@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer';
import {
  Database,
  Activity,
  Upload,
  BarChart3,
  Settings as SettingsIcon,
  Brain,
  Network,
  Code,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import './App.scss';
import Notification from './@components/notification/Notification';
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

interface ExtractionTask {
  taskId: string;
  fileName: string;
  status:
    | 'pending'
    | 'running'
    | 'processing'
    | 'completed'
    | 'failed'
    | 'awaiting_recommendations_approval';
  message: string;
  createdAt: string;
  completedAt?: string;
  timestamp?: string;
  progress?: number;
  results?: {
    entities: Entity[];
    relationships: Relationship[];
  };
  incrementalSummary?: IncrementalSummary;
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
  progress?: number;
  incremental_summary?: IncrementalSummary;
}

interface NavigationProps {
  activeTab: string;
  isCollapsed: boolean;
  onToggle: () => void;
}

// Navigation component
const Navigation: React.FC<NavigationProps> = ({ activeTab, isCollapsed, onToggle }) => {
  // #region agent log
  React.useEffect(() => {
    console.log('[DEBUG] Navigation rendered with props:', { activeTab, isCollapsed, hasOnToggle: !!onToggle });
    fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:Navigation',message:'Navigation component rendered',data:{activeTab,isCollapsed,hasOnToggle:!!onToggle},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'E'})}).catch(()=>{});
  }, [activeTab, isCollapsed, onToggle]);
  // #endregion

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
      id: 'architecture',
      label: 'Architecture Map',
      icon: <Network size={20} />,
      path: '/architecture',
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
          ref={(el) => {
            // #region agent log
            if (el) {
              setTimeout(() => {
                const rect = el.getBoundingClientRect();
                const styles = window.getComputedStyle(el);
                const parent = el.parentElement;
                const parentStyles = parent ? window.getComputedStyle(parent) : null;
                const data = {
                  buttonExists: true,
                  display: styles.display,
                  visibility: styles.visibility,
                  opacity: styles.opacity,
                  width: rect.width,
                  height: rect.height,
                  top: rect.top,
                  left: rect.left,
                  right: rect.right,
                  bottom: rect.bottom,
                  zIndex: styles.zIndex,
                  position: styles.position,
                  parentDisplay: parentStyles?.display,
                  parentOverflow: parentStyles?.overflow,
                  parentWidth: parent ? parent.getBoundingClientRect().width : 0,
                  inViewport: rect.width > 0 && rect.height > 0 && rect.top >= 0
                };
                console.log('[DEBUG] Button ref - DOM element details:', data);
                fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:nav-toggle-ref',message:'Button DOM element details',data,timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'A,B,C,D,F'})}).catch(()=>{});
              }, 100);
            } else {
              console.log('[DEBUG] Button ref - element is NULL!');
              fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:nav-toggle-ref',message:'Button element is NULL',data:{buttonExists:false},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'A'})}).catch(()=>{});
            }
            // #endregion
          }}
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
            flexShrink: 0
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
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [extractionTasks, setExtractionTasks] = useState<
    Record<string, ExtractionTask>
  >({});
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<GraphData>({
    nodes: [],
    links: [],
  });
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [isNavCollapsed, setIsNavCollapsed] = useState<boolean>(false);

  const showNotification = (message: string, type: 'success' | 'error' | 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const loadGraphData = useCallback(async (taskId: string) => {
    try {
      console.log('Loading graph data for task:', taskId);

      // First try to get graph data from the dedicated graph API endpoint
      try {
        const graphDataResponse =
          await ontologyAPI.getGraphVisualization(taskId);
        console.log('Graph data from API:', graphDataResponse);

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
      } catch (apiError) {
        console.log(
          'Graph API not available, loading from entities and relationships:',
          apiError
        );
      }

      // Fallback: Load entities and relationships directly from API (same as Ontology Results)
      console.log('Loading entities and relationships from API...');

      // Load entities and relationships the same way as Ontology Results
      const entitiesData = await ontologyAPI.getEntities(taskId, 100, 0);
      const relationshipsData = await ontologyAPI.getRelationships(
        taskId,
        100,
        0
      );

      const entities = entitiesData.items || [];
      const relationships = relationshipsData.items || [];

      console.log('Loaded entities:', entities.length);
      console.log('Loaded relationships:', relationships.length);
      console.log('Sample entity:', entities[0]);
      console.log('Sample relationship:', relationships[0]);
      console.log('All relationships:', relationships);
      console.log(
        'Entity names:',
        entities.map(e => e.name)
      );
      console.log(
        'Entity IDs:',
        entities.map(e => ({ name: e.name, id: e.id, idType: typeof e.id }))
      );
      console.log(
        'Entity types:',
        entities.map(e => ({ name: e.name, entityType: e.entity_type }))
      );

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

      // Debug: Log all node IDs
      console.log(
        'Node IDs:',
        nodes.map(n => n.id)
      );

      const links: GraphLink[] = relationships
        .map(rel => {
          console.log('Processing relationship:', rel);

          // The API returns source_entity and target_entity (names) instead of IDs
          // We need to find the corresponding entity IDs by matching the names
          const sourceEntity = entities.find(
            entity => entity.name === rel.source_entity
          );
          const targetEntity = entities.find(
            entity => entity.name === rel.target_entity
          );

          if (!sourceEntity || !targetEntity) {
            console.warn('Could not find entities for relationship:', rel);
            console.warn(
              'Source entity name:',
              rel.source_entity,
              'Found:',
              sourceEntity
            );
            console.warn(
              'Target entity name:',
              rel.target_entity,
              'Found:',
              targetEntity
            );
            return null;
          }

          const link = {
            id: rel.id || `rel-${sourceEntity.id}-${targetEntity.id}`,
            source: String(sourceEntity.id || `entity-${sourceEntity.name}`),
            target: String(targetEntity.id || `entity-${targetEntity.name}`),
            label: rel.relationship_type,
            confidence: rel.confidence,
          };
          console.log('Created link:', link);
          console.log(
            'Source entity ID type:',
            typeof sourceEntity.id,
            'Value:',
            sourceEntity.id
          );
          console.log(
            'Target entity ID type:',
            typeof targetEntity.id,
            'Value:',
            targetEntity.id
          );
          console.log(
            'Link source type:',
            typeof link.source,
            'Value:',
            link.source
          );
          console.log(
            'Link target type:',
            typeof link.target,
            'Value:',
            link.target
          );
          return link;
        })
        .filter(Boolean) as GraphLink[];

      // Debug: Log all relationship references
      console.log(
        'Relationship source IDs:',
        links.map(l => l.source)
      );
      console.log(
        'Relationship target IDs:',
        links.map(l => l.target)
      );

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

      console.log(
        `Filtered ${links.length - validLinks.length} invalid relationships`
      );

      console.log('Final graph data:', { nodes, links: validLinks });
      console.log('Number of valid links:', validLinks.length);
      console.log('Valid links details:', validLinks);

      // Test: Create a simple link to see if the issue is with our data or ForceGraph2D
      const testLink = {
        id: 'test-link',
        source: 'test-source',
        target: 'test-target',
        label: 'Test Link',
        confidence: 0.9,
      };
      console.log('Test link:', testLink);
      console.log('Test link source type:', typeof testLink.source);

      setGraphData({ nodes, links: validLinks });
    } catch (error) {
      console.error('Failed to load graph data:', error);
      // Set empty graph data on error
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

    setExtractionTasks(prev => {
      const existingTask = prev[wsData.task_id!];

      const baseTask: ExtractionTask =
        existingTask ||
        ({
          taskId: wsData.task_id!,
          fileName: `Task ${wsData.task_id!.substring(0, 8)}...`,
          status: 'pending',
          message: wsData.message || 'Task update received',
          createdAt: wsData.timestamp || new Date().toISOString(),
          progress: wsData.progress ?? 0,
          incrementalSummary: wsData.incremental_summary,
        } as ExtractionTask);

      const updatedTask: ExtractionTask = {
        ...baseTask,
        status: (wsData.status as ExtractionTask['status']) || baseTask.status,
        message: wsData.message || baseTask.message,
        timestamp: wsData.timestamp || baseTask.timestamp,
        progress: wsData.progress ?? baseTask.progress,
        incrementalSummary:
          wsData.incremental_summary ?? baseTask.incrementalSummary,
      };

      return {
        ...prev,
        [wsData.task_id!]: updatedTask,
      };
    });
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
          const tasksMap: Record<string, ExtractionTask> = {};
          data.tasks.forEach((task: any) => {
            tasksMap[task.task_id] = {
              taskId: task.task_id,
              fileName: `Task ${task.task_id.substring(0, 8)}...`,
              status: task.status,
              message: task.message || 'Task loaded from API',
              createdAt: task.created_at,
              completedAt: task.completed_at,
            };
          });
          setExtractionTasks(tasksMap);

          // Set the most recent completed task as active
          const completedTasks = data.tasks.filter(
            (t: any) => t.status === 'completed'
          );
          if (completedTasks.length > 0) {
            const mostRecent = completedTasks.sort(
              (a: any, b: any) =>
                new Date(b.created_at).getTime() -
                new Date(a.created_at).getTime()
            )[0];
            setActiveTaskId(mostRecent.task_id);
          }
        }
      }
    } catch (error) {
      console.error('Error loading available tasks:', error);
    }
  }, []);

  useEffect(() => {
    wsService.connect();

    const handleConnected = () => console.log('WebSocket connected');
    const handleDisconnected = () => console.log('WebSocket disconnected');

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
        console.log('Task completed, loading graph data:', task.taskId);
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
    (taskId: string, file: UploadedFile) => {
      setExtractionTasks(prev => ({
        ...prev,
        [taskId]: {
          taskId,
          fileName: file.name,
          status: 'pending',
          message: 'Task created and queued',
          createdAt: new Date().toISOString(),
          progress: 0,
          incrementalSummary: undefined,
        },
      }));

      // Set as active task (always use the most recent upload)
      setActiveTaskId(taskId);
    },
    [activeTaskId]
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
    if (location.pathname === '/graph') {
      if (activeTaskId) {
        console.log(
          'Navigated to graph view, loading graph data for active task:',
          activeTaskId
        );
        loadGraphData(activeTaskId);
      } else {
        // If no active task ID, try to load data from the most recent completed task
        console.log(
          'No active task ID, attempting to load graph data without task filter'
        );
        loadGraphDataWithoutTask();
      }
    }
  }, [location.pathname, activeTaskId, loadGraphData]);

  const loadGraphDataWithoutTask = useCallback(async () => {
    try {
      console.log(
        'No active task - showing empty graph (no data from current session)'
      );

      // When there's no active task, show empty graph to avoid confusion
      // This prevents showing data from previous sessions
      setGraphData({ nodes: [], links: [] });
    } catch (error) {
      console.error('Error loading graph data without task:', error);
      setGraphData({ nodes: [], links: [] });
    }
  }, []);

  // Determine active tab based on location
  const getActiveTab = (): string => {
    const path = location.pathname;
    if (path === '/') return 'upload';
    if (path === '/results') return 'results';
    if (path === '/graph') return 'graph';
    if (path === '/architecture') return 'architecture';
    if (path === '/metrics') return 'metrics';
    if (path === '/settings') return 'settings';
    return 'upload';
  };

  const activeTab = getActiveTab();
  const activeTaskSummary =
    activeTaskId && extractionTasks[activeTaskId]
      ? extractionTasks[activeTaskId]?.incrementalSummary
      : undefined;

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
            // #region agent log
            fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:MainContent-onToggle',message:'Toggle function called',data:{currentState:isNavCollapsed,newState:!isNavCollapsed},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
            // #endregion
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
                            <strong>Incremental Summary:</strong>{' '}
                            Entities +{activeTaskSummary.added_entities} · Δ
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
                          } catch (error) {
                            console.error(
                              'Error loading all graph data:',
                              error
                            );
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
                    onEdgeClick={edge => console.log('Edge clicked:', edge)}
                    activeTaskId={activeTaskId}
                    onGraphUpdate={() => {
                      if (activeTaskId) {
                        loadGraphData(activeTaskId);
                        showNotification('Graph updated with the latest data!', 'info');
                      }
                    }}
                  />
                </div>
              }
            />

            <Route path="/architecture" element={<ArchitectureMap />} />
            
            <Route path="/code-architecture" element={<CodeArchitectureViewer />} />

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
