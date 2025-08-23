import React, { useState, useEffect } from 'react';
import { ontologyAPI, apiUtils } from '../services/api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts';
import { Activity, Database, Brain, Link, TrendingUp, AlertTriangle, CheckCircle, Clock, RefreshCw } from 'lucide-react';
import './SystemMetrics.css';

const SystemMetrics = () => {
  const [metrics, setMetrics] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(30); // seconds

  useEffect(() => {
    loadMetrics();
    
    if (autoRefresh) {
      const interval = setInterval(loadMetrics, refreshInterval * 1000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval]);

  const loadMetrics = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Load metrics and health in parallel
      const [metricsData, healthData] = await Promise.all([
        ontologyAPI.getMetrics(),
        ontologyAPI.healthCheck()
      ]);
      
      setMetrics(metricsData);
      setHealth(healthData);
    } catch (error) {
      console.error('Failed to load metrics:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const getHealthColor = (status) => {
    switch (status) {
      case 'healthy': return '#28a745';
      case 'unhealthy': return '#dc3545';
      case 'degraded': return '#ffc107';
      default: return '#6c757d';
    }
  };

  const getHealthIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircle size={20} />;
      case 'unhealthy': return <AlertTriangle size={20} />;
      case 'degraded': return <Clock size={20} />;
      default: return <AlertTriangle size={20} />;
    }
  };

  if (loading && !metrics) {
    return (
      <div className="system-metrics loading">
        <RefreshCw className="spinner" size={24} />
        <p>Loading system metrics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="system-metrics error">
        <AlertTriangle size={48} />
        <h3>Failed to Load Metrics</h3>
        <p>{error}</p>
        <button onClick={loadMetrics} className="btn-retry">
          <RefreshCw size={16} /> Retry
        </button>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="system-metrics empty">
        <Activity size={48} />
        <h3>No Metrics Available</h3>
        <p>System metrics are not available at the moment.</p>
      </div>
    );
  }

  // Prepare chart data
  const taskStatusData = [
    { name: 'Completed', value: metrics.system_metrics?.completed_tasks || 0, color: '#28a745' },
    { name: 'Failed', value: metrics.system_metrics?.failed_tasks || 0, color: '#dc3545' },
    { name: 'Pending', value: (metrics.system_metrics?.total_tasks || 0) - (metrics.system_metrics?.completed_tasks || 0) - (metrics.system_metrics?.failed_tasks || 0), color: '#ffc107' }
  ].filter(item => item.value > 0);

  const performanceData = [
    { name: 'Avg Processing Time', value: metrics.extraction_metrics?.average_processing_time || 0, unit: 's' },
    { name: 'Total Entities', value: metrics.extraction_metrics?.total_entities_extracted || 0, unit: '' },
    { name: 'Total Relationships', value: metrics.extraction_metrics?.total_relationships_discovered || 0, unit: '' }
  ];

  const qualityData = [
    { name: 'Entity Confidence', value: metrics.quality_metrics?.average_entity_confidence || 0, color: '#007bff' },
    { name: 'Relationship Confidence', value: metrics.quality_metrics?.average_relationship_confidence || 0, color: '#28a745' },
    { name: 'Data Coverage', value: metrics.quality_metrics?.data_coverage || 0, color: '#ffc107' }
  ];

  return (
    <div className="system-metrics">
      <div className="metrics-header">
        <h3><Activity size={20} /> System Metrics & Health</h3>
        
        <div className="metrics-controls">
          <label>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh
          </label>
          
          {autoRefresh && (
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(parseInt(e.target.value))}
            >
              <option value={15}>15s</option>
              <option value={30}>30s</option>
              <option value={60}>1m</option>
              <option value={300}>5m</option>
            </select>
          )}
          
          <button onClick={loadMetrics} className="btn-refresh">
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </div>

      {/* Health Status */}
      <div className="health-section">
        <h4><CheckCircle size={16} /> System Health</h4>
        <div className="health-grid">
          <div className="health-item">
            <div className="health-status" style={{ color: getHealthColor(health?.status) }}>
              {getHealthIcon(health?.status)}
              <span className="status-text">{health?.status || 'Unknown'}</span>
            </div>
            <small>Overall Status</small>
          </div>
          
          <div className="health-item">
            <div className="health-detail">
              <span className="label">Version:</span>
              <span className="value">{health?.version || 'N/A'}</span>
            </div>
            <small>API Version</small>
          </div>
          
          <div className="health-item">
            <div className="health-detail">
              <span className="label">Last Check:</span>
              <span className="value">{apiUtils.formatTimestamp(health?.timestamp)}</span>
            </div>
            <small>Health Check Time</small>
          </div>
        </div>

        {/* Dependencies Health */}
        {health?.dependencies && (
          <div className="dependencies-health">
            <h5>Dependencies</h5>
            <div className="dependencies-grid">
              {Object.entries(health.dependencies).map(([service, status]) => (
                <div key={service} className="dependency-item">
                  <span className="service-name">{service}</span>
                  <span 
                    className={`status-badge ${status === 'healthy' ? 'healthy' : 'unhealthy'}`}
                  >
                    {status === 'healthy' ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
                    {status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* System Overview */}
      <div className="metrics-section">
        <h4><Database size={16} /> System Overview</h4>
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-icon">
              <Database size={24} />
            </div>
            <div className="metric-content">
              <div className="metric-value">{metrics.system_metrics?.total_tasks || 0}</div>
              <div className="metric-label">Total Tasks</div>
            </div>
          </div>
          
          <div className="metric-card">
            <div className="metric-icon">
              <CheckCircle size={24} />
            </div>
            <div className="metric-content">
              <div className="metric-value">{metrics.system_metrics?.completed_tasks || 0}</div>
              <div className="metric-label">Completed Tasks</div>
            </div>
          </div>
          
          <div className="metric-card">
            <div className="metric-icon">
              <AlertTriangle size={24} />
            </div>
            <div className="metric-content">
              <div className="metric-value">{metrics.system_metrics?.failed_tasks || 0}</div>
              <div className="metric-label">Failed Tasks</div>
            </div>
          </div>
          
          <div className="metric-card">
            <div className="metric-icon">
              <TrendingUp size={24} />
            </div>
            <div className="metric-content">
              <div className="metric-value">
                {Math.round((metrics.system_metrics?.success_rate || 0) * 100)}%
              </div>
              <div className="metric-label">Success Rate</div>
            </div>
          </div>
        </div>
      </div>

      {/* Task Status Chart */}
      {taskStatusData.length > 0 && (
        <div className="chart-section">
          <h4><BarChart size={16} /> Task Status Distribution</h4>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={taskStatusData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {taskStatusData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Performance Metrics */}
      <div className="chart-section">
        <h4><TrendingUp size={16} /> Performance Metrics</h4>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={performanceData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip formatter={(value, name) => [value, name]} />
            <Bar dataKey="value" fill="#007bff" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Quality Metrics */}
      <div className="chart-section">
        <h4><Brain size={16} /> Quality Metrics</h4>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={qualityData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis domain={[0, 1]} />
            <Tooltip formatter={(value) => [Math.round(value * 100) + '%', 'Confidence']} />
            <Line type="monotone" dataKey="value" stroke="#007bff" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Extraction Details */}
      <div className="metrics-section">
        <h4><Brain size={16} /> Extraction Details</h4>
        <div className="extraction-details">
          <div className="detail-row">
            <span className="label">Average Processing Time:</span>
            <span className="value">
              {metrics.extraction_metrics?.average_processing_time?.toFixed(2) || '0'} seconds
            </span>
          </div>
          
          <div className="detail-row">
            <span className="label">Total Entities Extracted:</span>
            <span className="value">
              {metrics.extraction_metrics?.total_entities_extracted?.toLocaleString() || '0'}
            </span>
          </div>
          
          <div className="detail-row">
            <span className="label">Total Relationships Discovered:</span>
            <span className="value">
              {metrics.extraction_metrics?.total_relationships_discovered?.toLocaleString() || '0'}
            </span>
          </div>
          
          <div className="detail-row">
            <span className="label">Average Entity Confidence:</span>
            <span className="value">
              {Math.round((metrics.quality_metrics?.average_entity_confidence || 0) * 100)}%
            </span>
          </div>
          
          <div className="detail-row">
            <span className="label">Average Relationship Confidence:</span>
            <span className="value">
              {Math.round((metrics.quality_metrics?.average_relationship_confidence || 0) * 100)}%
            </span>
          </div>
          
          <div className="detail-row">
            <span className="label">Data Coverage:</span>
            <span className="value">
              {Math.round((metrics.quality_metrics?.data_coverage || 0) * 100)}%
            </span>
          </div>
        </div>
      </div>

      {/* Last Updated */}
      <div className="metrics-footer">
        <small>
          Last updated: {apiUtils.formatTimestamp(metrics.timestamp)}
        </small>
      </div>
    </div>
  );
};

export default SystemMetrics;
