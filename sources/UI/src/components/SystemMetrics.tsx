import React, { useState, useEffect } from 'react';
import { ontologyAPI, apiUtils } from '../services/api';
import {
  Activity,
  Database,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
  RefreshCw,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  Cell,
  PieChart,
  Pie,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';
import {
  SystemMetrics as SystemMetricsType,
  HealthStatus,
  ChartData,
} from '../types';
import './SystemMetrics.css';

const SystemMetrics: React.FC = () => {
  const [metrics, setMetrics] = useState<SystemMetricsType | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [metricsData, healthData] = await Promise.all([
        ontologyAPI.getMetrics(),
        ontologyAPI.healthCheck(),
      ]);

      setMetrics(metricsData);
      setHealth(healthData);
    } catch (error: unknown) {
      setError((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const getHealthColor = (status: string): string => {
    switch (status) {
      case 'healthy':
        return '#28a745';
      case 'unhealthy':
        return '#dc3545';
      case 'degraded':
        return '#ffc107';
      default:
        return '#6c757d';
    }
  };

  const getHealthIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle size={16} />;
      case 'unhealthy':
        return <AlertTriangle size={16} />;
      case 'degraded':
        return <Clock size={16} />;
      default:
        return <RefreshCw size={16} />;
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (autoRefresh) {
      interval = setInterval(loadData, 30000); // Refresh every 30 seconds
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  if (loading && !metrics) {
    return (
      <div className="metrics-loading">
        <RefreshCw className="loading-icon" />
        <p>Loading system metrics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="metrics-error">
        <AlertTriangle size={48} />
        <h3>Error Loading Metrics</h3>
        <p>{error}</p>
        <button onClick={loadData} className="retry-button">
          <RefreshCw size={16} />
          Retry
        </button>
      </div>
    );
  }

  if (!metrics || !health) {
    return (
      <div className="no-metrics">
        <Database size={48} />
        <h3>No Metrics Available</h3>
        <p>System metrics are not available at this time.</p>
      </div>
    );
  }

  // Chart data preparation
  const taskData: ChartData[] = [
    {
      name: 'Completed',
      value: metrics.system_metrics?.completed_tasks || 0,
      color: '#28a745',
    },
    {
      name: 'Failed',
      value: metrics.system_metrics?.failed_tasks || 0,
      color: '#dc3545',
    },
    {
      name: 'Pending',
      value:
        (metrics.system_metrics?.total_tasks || 0) -
        (metrics.system_metrics?.completed_tasks || 0) -
        (metrics.system_metrics?.failed_tasks || 0),
      color: '#ffc107',
    },
  ];

  const qualityData: ChartData[] = [
    {
      name: 'Entity Confidence',
      value: metrics.quality_metrics?.average_entity_confidence || 0,
      color: '#007bff',
    },
    {
      name: 'Relationship Confidence',
      value: metrics.quality_metrics?.average_relationship_confidence || 0,
      color: '#28a745',
    },
    {
      name: 'Data Coverage',
      value: metrics.quality_metrics?.data_coverage || 0,
      color: '#ffc107',
    },
  ];

  return (
    <div className="system-metrics">
      {/* Header Controls */}
      <div className="metrics-header">
        <div className="header-info">
          <h2>System Metrics Dashboard</h2>
          <p>Real-time monitoring of system performance and health</p>
        </div>

        <div className="header-controls">
          <label className="auto-refresh-toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh
          </label>

          <button
            onClick={loadData}
            className="refresh-button"
            disabled={loading}
          >
            <RefreshCw className={loading ? 'spinning' : ''} size={16} />
            Refresh
          </button>
        </div>
      </div>

      {/* System Health Overview */}
      <div className="health-overview">
        <div className="health-card">
          <div className="health-header">
            <h3>System Health</h3>
            <div
              className="health-status"
              style={{ color: getHealthColor(health?.status || 'unknown') }}
            >
              {getHealthIcon(health?.status || 'unknown')}
              <span className="status-text">{health?.status || 'Unknown'}</span>
            </div>
          </div>

          <div className="health-details">
            <div className="health-item">
              <span className="label">Version:</span>
              <span className="value">{health?.version || 'N/A'}</span>
            </div>

            <div className="health-item">
              <span className="label">Last Check:</span>
              <span className="value">
                {health?.timestamp
                  ? apiUtils.formatTimestamp(health.timestamp)
                  : 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Service Dependencies */}
        {health?.dependencies && (
          <div className="dependencies-card">
            <h4>Service Dependencies</h4>
            <div className="dependencies-list">
              {Object.entries(health.dependencies).map(([service, status]) => (
                <div key={service} className="dependency-item">
                  <span className="service-name">{service}</span>
                  <span
                    className={`service-status ${status ? 'healthy' : 'unhealthy'}`}
                    style={{ color: status ? '#28a745' : '#dc3545' }}
                  >
                    {status ? 'Healthy' : 'Unhealthy'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Key Metrics */}
      <div className="key-metrics">
        <div className="metric-card">
          <div className="metric-header">
            <Database size={24} />
            <span>Total Tasks</span>
          </div>
          <div className="metric-value">
            {metrics.system_metrics?.total_tasks || 0}
          </div>
          <div className="metric-label">All time</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <CheckCircle size={24} />
            <span>Completed</span>
          </div>
          <div className="metric-value">
            {metrics.system_metrics?.completed_tasks || 0}
          </div>
          <div className="metric-label">Successfully processed</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <AlertTriangle size={24} />
            <span>Failed</span>
          </div>
          <div className="metric-value">
            {metrics.system_metrics?.failed_tasks || 0}
          </div>
          <div className="metric-label">Processing failures</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <TrendingUp size={24} />
            <span>Success Rate</span>
          </div>
          <div className="metric-value">
            {Math.round((metrics.system_metrics?.success_rate || 0) * 100)}%
          </div>
          <div className="metric-label">Overall performance</div>
        </div>
      </div>

      {/* Charts Section */}
      <div className="charts-section">
        {/* Task Distribution */}
        <div className="chart-card">
          <h4>
            <Activity size={16} /> Task Status Distribution
          </h4>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={taskData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={80}
                paddingAngle={5}
                dataKey="value"
                label={({ name, value }) => `${name}: ${value}`}
              >
                {taskData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Quality Metrics */}
        <div className="chart-card">
          <h4>
            <TrendingUp size={16} /> Quality Metrics
          </h4>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={qualityData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis domain={[0, 1]} />
              <Tooltip
                formatter={(value: unknown) => [
                  Math.round(Number(value) * 100) + '%',
                  'Confidence',
                ]}
              />
              <Bar dataKey="value" fill="#007bff" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Performance Stats */}
      <div className="performance-stats">
        <div className="stat-item">
          <span className="stat-label">Average Processing Time</span>
          <span className="stat-value">
            {metrics.extraction_metrics?.average_processing_time?.toFixed(2) ||
              '0'}{' '}
            seconds
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Total Entities Extracted</span>
          <span className="stat-value">
            {metrics.extraction_metrics?.total_entities_extracted?.toLocaleString() ||
              '0'}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Total Relationships Discovered</span>
          <span className="stat-value">
            {metrics.extraction_metrics?.total_relationships_discovered?.toLocaleString() ||
              '0'}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Average Entity Confidence</span>
          <span className="stat-value">
            {Math.round(
              (metrics.quality_metrics?.average_entity_confidence || 0) * 100
            )}
            %
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Average Relationship Confidence</span>
          <span className="stat-value">
            {Math.round(
              (metrics.quality_metrics?.average_relationship_confidence || 0) *
                100
            )}
            %
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Data Coverage</span>
          <span className="stat-value">
            {Math.round((metrics.quality_metrics?.data_coverage || 0) * 100)}%
          </span>
        </div>
      </div>

      {/* Footer */}
      <div className="metrics-footer">
        <small>
          Last updated: {apiUtils.formatTimestamp(metrics.timestamp)}
        </small>
      </div>
    </div>
  );
};

export default SystemMetrics;
