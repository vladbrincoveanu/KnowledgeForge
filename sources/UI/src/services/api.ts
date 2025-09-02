import axios, { AxiosInstance, AxiosResponse } from 'axios';

// TypeScript interfaces
interface ExtractConfig {
  [key: string]: unknown;
}

interface ExtractResponse {
  task_id: string;
  status: string;
  message?: string;
}

interface ExtractionStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  message?: string;
  result?: unknown;
}

interface Entity {
  id?: string;
  name: string;
  entity_type: string;
  confidence: number;
  source_columns?: string[];
  source_value?: string;
  attributes?: Record<string, any>;
}

interface Relationship {
  id?: string;
  source_entity_id?: string;
  target_entity_id?: string;
  relationship_type: string;
  confidence: number;
  source_columns?: string[];
  attributes?: Record<string, any>;
}

interface PaginatedResponse<T> {
  items?: T[];
  entities?: T[];
  relationships?: T[];
  total?: number;
  total_count?: number;
  limit?: number;
  offset?: number;
  extraction_metadata?: {
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

interface AxiosErrorResponse {
  response?: {
    status: number;
    statusText: string;
    data: unknown;
    headers: Record<string, string>;
  };
  message: string;
}

interface GraphVisualization {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties?: Record<string, unknown>;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties?: Record<string, unknown>;
}

interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  active_tasks: number;
}

interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  services: Record<string, boolean>;
  timestamp: string;
}

interface ProcessedFile {
  name: string;
  headers: string[];
  data: Record<string, string>[];
  size: number;
  rowCount: number;
  type: string;
}

interface UploadResponse {
  file_path: string;
  file_name: string;
  file_size: number;
  content_type: string;
  message: string;
}

interface FeedbackData {
  type: 'positive' | 'negative';
  entity_id?: string;
  relationship_id?: string;
  comment?: string;
}

// API configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_KEY = import.meta.env.VITE_API_KEY || 'test-api-key-12345';

// Create axios instance with default configuration
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${API_KEY}`,
  },
});

// Create a separate axios instance for file uploads (without default Content-Type)
const fileUploadApi: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // Longer timeout for file uploads
  headers: {
    Authorization: `Bearer ${API_KEY}`,
    // No Content-Type header - let browser set it for FormData
  },
});

// Request interceptor to add API key
api.interceptors.request.use(
  config => {
    config.headers.Authorization = `Bearer ${API_KEY}`;
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Request interceptor for file upload API
fileUploadApi.interceptors.request.use(
  config => {
    config.headers.Authorization = `Bearer ${API_KEY}`;
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      console.error('API authentication failed. Please check your API key.');
    }
    return Promise.reject(error);
  }
);

// Response interceptor for file upload API
fileUploadApi.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      console.error('API authentication failed. Please check your API key.');
    }
    return Promise.reject(error);
  }
);

// Ontology Extraction API
export const ontologyAPI = {
  // Extract ontology from CSV file
  extractOntology: async (
    filePath: string,
    extractionConfig: ExtractConfig = {}
  ): Promise<ExtractResponse> => {
    const response: AxiosResponse<ExtractResponse> = await api.post(
      '/v1/extract/',
      {
        file_path: filePath,
        extraction_config: extractionConfig,
      }
    );
    return response.data;
  },

  // Get extraction task status
  getExtractionStatus: async (taskId: string): Promise<ExtractionStatus> => {
    const response: AxiosResponse<ExtractionStatus> = await api.get(
      `/v1/extract/${taskId}`
    );
    return response.data;
  },

  // Get entities with pagination
  getEntities: async (
    taskId: string | null = null,
    limit = 100,
    offset = 0
  ): Promise<PaginatedResponse<Entity>> => {
    const params: Record<string, string | number> = { limit, offset };
    if (taskId) params.task_id = taskId;

    const response: AxiosResponse<PaginatedResponse<Entity>> = await api.get(
      '/v1/entities',
      { params }
    );
    const data = response.data;
    // Normalize the response to match expected format
    return {
      items: data.entities || [],
      total: data.total_count || 0,
      limit: data.extraction_metadata?.limit || limit,
      offset: data.extraction_metadata?.offset || offset,
    };
  },

  // Get relationships with pagination
  getRelationships: async (
    taskId: string | null = null,
    limit = 100,
    offset = 0
  ): Promise<PaginatedResponse<Relationship>> => {
    const params: Record<string, string | number> = { limit, offset };
    if (taskId) params.task_id = taskId;

    const response: AxiosResponse<PaginatedResponse<Relationship>> =
      await api.get('/v1/relationships', { params });
    const data = response.data;
    // Normalize the response to match expected format
    return {
      items: data.relationships || [],
      total: data.total_count || 0,
      limit: data.extraction_metadata?.limit || limit,
      offset: data.extraction_metadata?.offset || offset,
    };
  },

  // Submit feedback
  submitFeedback: async (feedbackData: FeedbackData): Promise<unknown> => {
    const response: AxiosResponse<unknown> = await api.post(
      '/v1/feedback',
      feedbackData
    );
    return response.data;
  },

  // Get graph visualization
  getGraphVisualization: async (
    taskId: string
  ): Promise<GraphVisualization> => {
    const response: AxiosResponse<GraphVisualization> = await api.get(
      '/v1/graph/visualize',
      {
        params: { task_id: taskId },
      }
    );
    return response.data;
  },

  // Get system metrics
  getMetrics: async (): Promise<SystemMetrics> => {
    const response: AxiosResponse<SystemMetrics> = await api.get(
      '/v1/health/metrics'
    );
    return response.data;
  },

  // Health check
  healthCheck: async (): Promise<HealthStatus> => {
    const response: AxiosResponse<HealthStatus> =
      await api.get('/v1/health/');
    return response.data;
  },

  // Readiness check
  readinessCheck: async (): Promise<HealthStatus> => {
    const response: AxiosResponse<HealthStatus> = await api.get(
      '/v1/health/ready'
    );
    return response.data;
  },
};

// File Upload API (for local file processing)
export const fileAPI = {
  // Process local CSV file
  processLocalFile: async (file: File): Promise<ProcessedFile> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = event => {
        try {
          const csvContent = event.target?.result as string;
          const lines = csvContent.split('\n');
          const headers = lines[0].split(',').map(h => h.trim());
          const data = lines
            .slice(1)
            .filter(line => line.trim())
            .map(line => {
              const values = line.split(',').map(v => v.trim());
              const row: Record<string, string> = {};
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
            type: 'csv',
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
  uploadFile: async (file: File): Promise<UploadResponse> => {
    try {
      console.log(
        'Uploading file:',
        file.name,
        'Size:',
        file.size,
        'Type:',
        file.type
      );

      const formData = new FormData();
      formData.append('file', file);

      // For file uploads, we need to remove the default Content-Type header
      // and let the browser set it automatically with the boundary
      const response: AxiosResponse<UploadResponse> = await fileUploadApi.post(
        '/v1/extract/upload',
        formData
      );

      console.log('Upload response:', response.data);
      return response.data;
    } catch (error: unknown) {
      const axiosError = error as AxiosErrorResponse;
      console.error('Upload error details:', {
        status: axiosError.response?.status,
        statusText: axiosError.response?.statusText,
        data: axiosError.response?.data,
        headers: axiosError.response?.headers,
        message: axiosError.message,
      });
      throw error;
    }
  },
};

// WebSocket message types
interface WebSocketMessage {
  type: string;
  data?: unknown;
  timestamp?: string;
}

// WebSocket service for real-time updates
export class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts = 5;
  private readonly reconnectDelay = 1000;
  private readonly listeners = new Map<string, ((data?: unknown) => void)[]>();

  connect(): void {
    try {
      // Use direct WebSocket connection to backend since proxy doesn't handle WebSocket
      const wsUrl = API_BASE_URL === '/api' 
        ? 'ws://localhost:8000/ws' 
        : API_BASE_URL.replace('http', 'ws') + '/ws';
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.emit('connected');
      };

      this.ws.onmessage = event => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
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

      this.ws.onerror = error => {
        console.error('WebSocket error:', error);
        this.emit('error', error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(
        `Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`
      );

      setTimeout(() => {
        this.connect();
      }, this.reconnectDelay * this.reconnectAttempts);
    } else {
      console.error('Max reconnection attempts reached');
      this.emit('reconnect_failed');
    }
  }

  on(event: string, callback: (data?: unknown) => void): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)?.push(callback);
  }

  off(event: string, callback: (data?: unknown) => void): void {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event)!;
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  private emit(event: string, data?: unknown): void {
    if (this.listeners.has(event)) {
      this.listeners.get(event)?.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Error in event listener:', error);
        }
      });
    }
  }

  send(data: unknown): void {
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
  formatFileSize: (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },

  // Format confidence score
  formatConfidence: (confidence: number): string => {
    return Math.round(confidence * 100) + '%';
  },

  // Get confidence color
  getConfidenceColor: (confidence: number): string => {
    if (confidence >= 0.8) return '#28a745';
    if (confidence >= 0.6) return '#ffc107';
    return '#dc3545';
  },

  // Format timestamp
  formatTimestamp: (timestamp: string): string => {
    return new Date(timestamp).toLocaleString();
  },

  // Validate API response
  validateResponse: (response: unknown): unknown => {
    if (!response || typeof response !== 'object') {
      throw new Error('Invalid response format');
    }
    return response;
  },
};

export default api;
