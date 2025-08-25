import axios from 'axios';

// API configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_KEY = import.meta.env.VITE_API_KEY || 'test-api-key-12345';

// Create axios instance with default configuration
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${API_KEY}`
  }
});

// Create a separate axios instance for file uploads (without default Content-Type)
const fileUploadApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // Longer timeout for file uploads
  headers: {
    'Authorization': `Bearer ${API_KEY}`
    // No Content-Type header - let browser set it for FormData
  }
});

// Request interceptor to add API key
api.interceptors.request.use(
  (config) => {
    config.headers.Authorization = `Bearer ${API_KEY}`;
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Request interceptor for file upload API
fileUploadApi.interceptors.request.use(
  (config) => {
    config.headers.Authorization = `Bearer ${API_KEY}`;
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      console.error('API authentication failed. Please check your API key.');
    }
    return Promise.reject(error);
  }
);

// Response interceptor for file upload API
fileUploadApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      console.error('API authentication failed. Please check your API key.');
    }
    return Promise.reject(error);
  }
);

// Ontology Extraction API
export const ontologyAPI = {
  // Extract ontology from CSV file
  extractOntology: async (filePath, extractionConfig = {}) => {
    const response = await api.post('/extract', {
      file_path: filePath,
      extraction_config: extractionConfig
    });
    return response.data;
  },

  // Get extraction task status
  getExtractionStatus: async (taskId) => {
    const response = await api.get(`/extract/${taskId}`);
    return response.data;
  },

  // Get entities with pagination
  getEntities: async (taskId = null, limit = 100, offset = 0) => {
    const params = { limit, offset };
    if (taskId) params.task_id = taskId;
    
    const response = await api.get('/entities', { params });
    return response.data;
  },

  // Get relationships with pagination
  getRelationships: async (taskId = null, limit = 100, offset = 0) => {
    const params = { limit, offset };
    if (taskId) params.task_id = taskId;
    
    const response = await api.get('/relationships', { params });
    return response.data;
  },

  // Submit feedback
  submitFeedback: async (feedbackData) => {
    const response = await api.post('/feedback', feedbackData);
    return response.data;
  },

  // Get graph visualization
  getGraphVisualization: async (taskId) => {
    const response = await api.get('/graph/visualize', {
      params: { task_id: taskId }
    });
    return response.data;
  },

  // Get system metrics
  getMetrics: async () => {
    const response = await api.get('/metrics');
    return response.data;
  },

  // Health check
  healthCheck: async () => {
    const response = await api.get('/health');
    return response.data;
  },

  // Readiness check
  readinessCheck: async () => {
    const response = await api.get('/ready');
    return response.data;
  }
};

// File Upload API (for local file processing)
export const fileAPI = {
  // Process local CSV file
  processLocalFile: async (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (event) => {
        try {
          const csvContent = event.target.result;
          const lines = csvContent.split('\n');
          const headers = lines[0].split(',').map(h => h.trim());
          const data = lines.slice(1).filter(line => line.trim()).map(line => {
            const values = line.split(',').map(v => v.trim());
            const row = {};
            headers.forEach((header, index) => {
              row[header] = values[index] || '';
            });
            return row;
          });

          resolve({
            name: file.name,
            headers,
            data,
            size: file.size,
            rowCount: data.length,
            type: 'csv'
          });
        } catch (error) {
          reject(error);
        }
      };

      reader.onerror = () => reject(new Error('Failed to read file'));
      reader.readAsText(file);
    });
  },

  // Upload file to server
  uploadFile: async (file) => {
    try {
      console.log('Uploading file:', file.name, 'Size:', file.size, 'Type:', file.type);
      
      const formData = new FormData();
      formData.append('file', file);
      
      // For file uploads, we need to remove the default Content-Type header
      // and let the browser set it automatically with the boundary
      const response = await fileUploadApi.post('/upload', formData);
      
      console.log('Upload response:', response.data);
      return response.data;
    } catch (error) {
      console.error('Upload error details:', {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        headers: error.response?.headers,
        message: error.message
      });
      throw error;
    }
  }
};

// WebSocket service for real-time updates
export class WebSocketService {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.listeners = new Map();
  }

  connect() {
    try {
      const wsUrl = API_BASE_URL.replace('http', 'ws') + '/ws';
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.emit('connected');
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.emit('message', data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.emit('disconnected');
        this.attemptReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.emit('error', error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
      
      setTimeout(() => {
        this.connect();
      }, this.reconnectDelay * this.reconnectAttempts);
    } else {
      console.error('Max reconnection attempts reached');
      this.emit('reconnect_failed');
    }
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  off(event, callback) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Error in event listener:', error);
        }
      });
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}

// Export the WebSocket service instance
export const wsService = new WebSocketService();

// Utility functions
export const apiUtils = {
  // Format file size
  formatFileSize: (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },

  // Format confidence score
  formatConfidence: (confidence) => {
    return Math.round(confidence * 100) + '%';
  },

  // Get confidence color
  getConfidenceColor: (confidence) => {
    if (confidence >= 0.8) return '#28a745';
    if (confidence >= 0.6) return '#ffc107';
    return '#dc3545';
  },

  // Format timestamp
  formatTimestamp: (timestamp) => {
    return new Date(timestamp).toLocaleString();
  },

  // Validate API response
  validateResponse: (response) => {
    if (!response || typeof response !== 'object') {
      throw new Error('Invalid response format');
    }
    return response;
  }
};

export default api;
