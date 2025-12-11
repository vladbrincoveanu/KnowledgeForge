import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { IncrementalSummary } from '@/types';

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
  source_entity?: string; // Entity name
  target_entity?: string; // Entity name
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
// Use empty string to leverage Vite proxy, or explicit URL for direct connection
// Force empty string if VITE_API_URL contains 'api:' (Docker service name) which browser can't resolve
let apiBaseUrl = import.meta.env.VITE_API_URL || '';
if (apiBaseUrl.includes('api:') || apiBaseUrl.includes('://api')) {
  // Browser can't resolve Docker service names, use relative URLs to go through Vite proxy
  apiBaseUrl = '';
}
const API_BASE_URL = apiBaseUrl;
const API_KEY = import.meta.env.VITE_API_KEY || 'test-api-key-12345';

// #region agent log
const envDebugInfo = {
  API_BASE_URL,
  originalViteApiUrl: import.meta.env.VITE_API_URL,
  hasViteApiUrl: !!import.meta.env.VITE_API_URL,
  wasOverridden: (import.meta.env.VITE_API_URL || '').includes('api:'),
  allEnvKeys: Object.keys(import.meta.env).filter(k => k.startsWith('VITE_')),
  windowLocation: typeof window !== 'undefined' ? window.location.href : 'N/A',
};
console.log('[DEBUG] API Config:', envDebugInfo);
fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:127',message:'API configuration loaded',data:envDebugInfo,timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
// #endregion

// Create axios instance with default configuration
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL, // Empty string uses relative URLs (works with Vite proxy)
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
    // #region agent log
    if (config.url?.includes('extract-from-github')) {
      const fullUrl = config.baseURL ? `${config.baseURL}${config.url}` : config.url;
      fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:157',message:'Request interceptor - constructing request',data:{url:config.url,baseURL:config.baseURL,fullUrl,method:config.method,hasHeaders:!!config.headers,timeout:config.timeout},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
    }
    // #endregion
    return config;
  },
  error => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:165',message:'Request interceptor error',data:{errorMessage:error?.message},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
    // #endregion
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
  response => {
    // #region agent log
    if (response.config.url?.includes('extract-from-github')) {
      console.log('[DEBUG] Response interceptor - success:', { url: response.config.url, status: response.status });
    }
    // #endregion
    return response;
  },
  error => {
    // #region agent log
    console.error('[DEBUG] Response interceptor - error:', {
      message: error?.message,
      code: error?.code,
      status: error?.response?.status,
      url: error?.config?.url,
      baseURL: error?.config?.baseURL,
      responseData: error?.response?.data
    });
    // #endregion
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
      '/api/v1/extract/',
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
      `/api/v1/extract/${taskId}`
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
      '/api/v1/entities',
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
      await api.get('/api/v1/relationships', { params });
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
      '/api/v1/feedback',
      feedbackData
    );
    return response.data;
  },

  // Get graph visualization
  getGraphVisualization: async (
    taskId?: string
  ): Promise<GraphVisualization> => {
    const params = taskId ? { task_id: taskId } : {};
    const response: AxiosResponse<GraphVisualization> = await api.get(
      '/api/v1/graph/visualize',
      { params }
    );
    return response.data;
  },

  // Get system metrics
  getMetrics: async (): Promise<SystemMetrics> => {
    const response: AxiosResponse<SystemMetrics> =
      await api.get('/api/v1/health/metrics');
    return response.data;
  },

  // Health check
  healthCheck: async (): Promise<HealthStatus> => {
    const response: AxiosResponse<HealthStatus> = await api.get('/api/v1/health/');
    return response.data;
  },

  // Readiness check
  readinessCheck: async (): Promise<HealthStatus> => {
    const response: AxiosResponse<HealthStatus> =
      await api.get('/api/v1/health/ready');
    return response.data;
  },

};

// Service Extraction API
export const serviceExtractionAPI = {
  // Extract services from GitHub repository
  extractFromGitHub: async (githubUrl: string, useGit: boolean = true): Promise<ExtractResponse> => {
    // #region agent log
    // Runtime fix: Force empty baseURL if it contains Docker service name
    const currentBaseURL = api.defaults.baseURL || '';
    const fixedBaseURL = (currentBaseURL.includes('api:') || currentBaseURL.includes('://api')) ? '' : currentBaseURL;
    if (fixedBaseURL !== currentBaseURL) {
      api.defaults.baseURL = fixedBaseURL;
      fileUploadApi.defaults.baseURL = fixedBaseURL;
    }
    fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:311',message:'extractFromGitHub API call starting',data:{apiBaseURL:API_BASE_URL,currentBaseURL,fixedBaseURL,githubUrl,useGit,requestUrl:'/api/v1/services/extract-from-github'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    try {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:313',message:'About to make axios.post request',data:{url:'/api/v1/services/extract-from-github',baseURL:api.defaults.baseURL,timeout:api.defaults.timeout},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      const response: AxiosResponse<ExtractResponse> = await api.post(
        '/api/v1/services/extract-from-github',
        {
          github_url: githubUrl,
          use_git: useGit,
        }
      );
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:320',message:'axios.post request succeeded',data:{status:response.status,statusText:response.statusText,hasData:!!response.data,taskId:response.data?.task_id},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      return response.data;
    } catch (error: any) {
      // #region agent log
      const axiosErrorDetails = {
        message: error?.message,
        name: error?.name,
        code: error?.code,
        responseStatus: error?.response?.status,
        responseStatusText: error?.response?.statusText,
        responseData: error?.response?.data,
        requestURL: error?.config?.url,
        requestBaseURL: error?.config?.baseURL,
        requestMethod: error?.config?.method,
        isNetworkError: !error?.response && error?.message?.includes('Network'),
        isTimeout: error?.code === 'ECONNABORTED',
      };
      console.error('[DEBUG] extractFromGitHub error:', axiosErrorDetails);
      fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:322',message:'axios.post request failed',data:axiosErrorDetails,timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
      // #endregion
      throw error;
    }
  },

  // Extract services from ZIP file
  extractFromZip: async (file: File): Promise<ExtractResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response: AxiosResponse<ExtractResponse> = await fileUploadApi.post(
      '/api/v1/services/extract-from-zip',
      formData
    );
    return response.data;
  },

  // Extract services from local path
  extractFromPath: async (repoPath: string): Promise<ExtractResponse> => {
    const response: AxiosResponse<ExtractResponse> = await api.post(
      '/api/v1/services/extract-from-path',
      {
        repo_path: repoPath,
      }
    );
    return response.data;
  },

  // Get extraction status
  getExtractionStatus: async (taskId: string): Promise<ExtractionStatus> => {
    // #region agent log
    console.log('[DEBUG] getExtractionStatus called', { taskId, baseURL: api.defaults.baseURL, url: `/api/v1/services/extraction/${taskId}` });
    fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:345',message:'getExtractionStatus called',data:{taskId,baseURL:api.defaults.baseURL,requestUrl:`/api/v1/services/extraction/${taskId}`},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'F'})}).catch(()=>{});
    // #endregion
    try {
      const response: AxiosResponse<ExtractionStatus> = await api.get(
        `/api/v1/services/extraction/${taskId}`
      );
      // #region agent log
      console.log('[DEBUG] getExtractionStatus response', response.data);
      fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:350',message:'getExtractionStatus response received',data:{status:response.data.status,statusCode:response.status},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'F'})}).catch(()=>{});
      // #endregion
      return response.data;
    } catch (error: any) {
      // #region agent log
      console.error('[DEBUG] getExtractionStatus error', error);
      const errorDetails = {
        message: error?.message,
        status: error?.response?.status,
        statusText: error?.response?.statusText,
        data: error?.response?.data,
      };
      fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:357',message:'getExtractionStatus error',data:errorDetails,timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'F'})}).catch(()=>{});
      // #endregion
      throw error;
    }
  },

  // Get extraction results
  getExtractionResults: async (taskId: string): Promise<{
    task_id: string;
    repository: { url?: string; name?: string };
    statistics: { total_services: number; total_connections: number };
    services: any[];
    connections: any[];
    errors: string[];
    warnings: string[];
  }> => {
    const response = await api.get(`/api/v1/services/extraction/${taskId}/results`);
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
        '/api/v1/extract/upload',
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
  task_id?: string;
  status?: string;
  message?: string;
  progress?: number;
  incremental_summary?: IncrementalSummary;
  [key: string]: unknown;
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
      if (
        this.ws &&
        (this.ws.readyState === WebSocket.OPEN ||
          this.ws.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }

      // Use direct WebSocket connection to backend since proxy doesn't handle WebSocket
      const wsUrl =
        API_BASE_URL === '/api'
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
        this.ws = null;
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
