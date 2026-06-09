import React, { useState, useEffect, useCallback } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  Link,
  useLocation,
} from "react-router-dom";
import { Upload, Settings as SettingsIcon, Code } from "lucide-react";
import KFLogo from "./@components/KFLogo";
import "./App.scss";
import CodeArchitectureViewer from "./@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer";
import Notification from "./@components/notification/Notification";
import FileUploader from "./@components/upload-extract/FileUploader/FileUploader";
import Settings from "./@components/settings/Settings/Settings";
import LandingPage from "./@components/landing/LandingPage/LandingPage";
import { wsService } from "./services/api";
import { IncrementalSummary } from "@/types";
import { ReviewDashboard } from "./pages/ReviewDashboard";
import { RepoProvider } from "./@components/upload-extract/RepoProvider/RepoProvider";
import RepoExplorer from "./@components/upload-extract/RepoExplorer/RepoExplorer";

// TypeScript interfaces
interface NavItem {
  id: string;
  label: string;
  icon: React.ReactElement;
  path: string;
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
}

interface ExtractionTask {
  taskId: string;
  fileName: string;
  status: string;
  createdAt: string;
}

// Navigation component
const Navigation: React.FC<NavigationProps> = ({ activeTab }) => {
  const navItems: NavItem[] = [
    {
      id: "workspace",
      label: "Workspace",
      icon: <Upload size={20} />,
      path: "/workspace",
    },
    {
      id: "code-architecture",
      label: "Code Architecture",
      icon: <Code size={20} />,
      path: "/code-architecture",
    },
    {
      id: "settings",
      label: "Settings",
      icon: <SettingsIcon size={20} />,
      path: "/settings",
    },
  ];

  return (
    <nav className={`main-navigation ${activeTab === "home" ? "is-home" : ""}`}>
      <div className="nav-header">
        <div className="nav-brand">
          <KFLogo height={44} />
        </div>
      </div>
      <ul className="nav-list">
        {navItems.map((item) => (
          <li key={item.id}>
            <Link
              to={item.path}
              className={`nav-link ${activeTab === item.id ? "active" : ""}`}
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
  const [, setActiveTaskId] = useState<string | null>(null);
  const [notification, setNotification] = useState<{
    message: string;
    type: "success" | "error" | "info";
  } | null>(null);
  const [, setExtractionTasks] = useState<Record<string, ExtractionTask>>({});
  const [, setActiveTaskSummary] = useState<IncrementalSummary | null>(null);

  const showNotification = (
    message: string,
    type: "success" | "error" | "info",
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
        "http://localhost:8000/api/v1/extract/tasks",
      );
      if (response.ok) {
        const data = await response.json();
        if (data.tasks && data.tasks.length > 0) {
          // Set the most recent completed task as active
          const completedTasks = data.tasks.filter(
            (t: any) => t.status === "completed",
          );
          const tasksMap: Record<string, ExtractionTask> = {};
          data.tasks.forEach((t: any) => {
            tasksMap[t.task_id] = {
              taskId: t.task_id,
              fileName: t.file_name || t.filename || "Unknown",
              status: t.status,
              createdAt: t.created_at,
            };
          });
          setExtractionTasks(tasksMap);
          if (completedTasks.length > 0) {
            const mostRecent = completedTasks.sort(
              (a: any, b: any) =>
                new Date(b.created_at).getTime() -
                new Date(a.created_at).getTime(),
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

  // Determine active tab based on location
  const getActiveTab = (): string => {
    const path = location.pathname;
    if (path.startsWith("/workspace")) return "workspace";
    if (path.startsWith("/code-architecture")) return "code-architecture";
    if (path.startsWith("/settings")) return "settings";
    return "code-architecture";
  };

  const activeTab = getActiveTab();
  const isArchitectureRoute = activeTab === "code-architecture";
  const isLandingRoute = activeTab === "home";
  const shouldBootstrapExtraction =
    activeTab === "workspace" || activeTab === "code-architecture";

  useEffect(() => {
    if (!shouldBootstrapExtraction) {
      return;
    }

    const handleConnected = () => {};
    const handleDisconnected = () => {};

    wsService.on("message", handleWebSocketMessage);
    wsService.on("connected", handleConnected);
    wsService.on("disconnected", handleDisconnected);

    loadAvailableTasks();

    return () => {
      wsService.off("message", handleWebSocketMessage);
      wsService.off("connected", handleConnected);
      wsService.off("disconnected", handleDisconnected);
    };
  }, [handleWebSocketMessage, loadAvailableTasks, shouldBootstrapExtraction]);

  const handleExtractionStarted = useCallback((taskId: string) => {
    setActiveTaskId(taskId);
  }, []);

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
        <Navigation activeTab={activeTab} />

        <main
          className={`main-content ${
            isArchitectureRoute ? "architecture-main-content" : ""
          } ${isLandingRoute ? "landing-main-content" : ""}`}
        >
          <Routes>
            <Route
              path="/"
              element={<Navigate to="/code-architecture" replace />}
            />
            <Route
              path="/workspace"
              element={
                <div className="upload-section">
                  <div className="section-header">
                    <h1>Build the Risk Evidence Baseline</h1>
                    <p>
                      Bring in repository and operational exports to generate
                      the system map, supporting evidence, and board-facing
                      narrative.
                    </p>
                  </div>

                  <FileUploader
                    isProcessing={false}
                    onExtractionStarted={handleExtractionStarted}
                    showNotification={showNotification}
                  />

                  <RepoExplorer onExtractionStarted={handleExtractionStarted} />

                  <hr
                    style={{
                      margin: "2rem 0",
                      border: 0,
                      borderTop: "1px solid #e5e7eb",
                    }}
                  />
                  <section className="review-section">
                    <h2>Pending Review Items</h2>
                    <ReviewDashboard />
                  </section>
                </div>
              }
            />

            <Route
              path="/code-architecture"
              element={<CodeArchitectureViewer />}
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

            <Route
              path="/review/*"
              element={<Navigate to="/workspace" replace />}
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
    <RepoProvider>
      <Router>
        <MainContent />
      </Router>
    </RepoProvider>
  );
};

export default App;
