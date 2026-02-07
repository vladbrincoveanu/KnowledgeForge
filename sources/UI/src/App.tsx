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
import FileUploader from './@components/upload-extract/FileUploader/FileUploader';
import SystemMetrics from './@components/system-metrics/SystemMetrics/SystemMetrics';
import Settings from './@components/settings/Settings/Settings';
import CodeArchitectureViewer from './@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer';
import {
  Activity,
  Upload,
  Settings as SettingsIcon,
  Brain,
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
const Navigation: React.FC<NavigationProps> = ({
  activeTab,
  isCollapsed,
  onToggle,
}) => {
  // #region agent log
  React.useEffect(() => {
    console.log('[DEBUG] Navigation rendered with props:', {
      activeTab,
      isCollapsed,
      hasOnToggle: !!onToggle,
    });
    fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        location: 'App.tsx:Navigation',
        message: 'Navigation component rendered',
        data: { activeTab, isCollapsed, hasOnToggle: !!onToggle },
        timestamp: Date.now(),
        sessionId: 'debug-session',
        runId: 'run3',
        hypothesisId: 'E',
      }),
    }).catch(() => {});
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
          ref={el => {
            // #region agent log
            if (el) {
              setTimeout(() => {
                const rect = el.getBoundingClientRect();
                const styles = window.getComputedStyle(el);
                const parent = el.parentElement;
                const parentStyles = parent
                  ? window.getComputedStyle(parent)
                  : null;
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
                  parentWidth: parent
                    ? parent.getBoundingClientRect().width
                    : 0,
                  inViewport:
                    rect.width > 0 && rect.height > 0 && rect.top >= 0,
                };
                console.log('[DEBUG] Button ref - DOM element details:', data);
                fetch(
                  'http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',
                  {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      location: 'App.tsx:nav-toggle-ref',
                      message: 'Button DOM element details',
                      data,
                      timestamp: Date.now(),
                      sessionId: 'debug-session',
                      runId: 'run3',
                      hypothesisId: 'A,B,C,D,F',
                    }),
                  }
                ).catch(() => {});
              }, 100);
            } else {
              console.log('[DEBUG] Button ref - element is NULL!');
              fetch(
                'http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',
                {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    location: 'App.tsx:nav-toggle-ref',
                    message: 'Button element is NULL',
                    data: { buttonExists: false },
                    timestamp: Date.now(),
                    sessionId: 'debug-session',
                    runId: 'run3',
                    hypothesisId: 'A',
                  }),
                }
              ).catch(() => {});
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

  const showNotification = (
    message: string,
    type: 'success' | 'error' | 'info'
  ) => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

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
            // #region agent log
            fetch(
              'http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  location: 'App.tsx:MainContent-onToggle',
                  message: 'Toggle function called',
                  data: {
                    currentState: isNavCollapsed,
                    newState: !isNavCollapsed,
                  },
                  timestamp: Date.now(),
                  sessionId: 'debug-session',
                  runId: 'run1',
                  hypothesisId: 'E',
                }),
              }
            ).catch(() => {});
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
