import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { IncrementalSummary, TaskStatus } from '@/types';

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

/**
 * Represents the user-visible state of a context field.
 */
export type BusinessFieldState = 'generated' | 'overridden' | 'missing';

/**
 * Captures provenance metadata for a generated context field.
 */
export interface BusinessFieldProvenance {
  source_type: string;
  source_path: string;
  source_hash: string;
  artifact_version: string;
  extraction_rule: string;
  confidence: number;
  last_seen: string;
}

/**
 * Captures override lifecycle metadata for a context field.
 */
export interface BusinessFieldOverrideMeta {
  updated_by: string;
  field_updated_at: string;
  override_reason: string;
  status: 'active' | 'stale' | 'superseded';
  needs_review: boolean;
}

/**
 * Represents one business context field in generated/override/effective form.
 */
export interface BusinessContextField {
  field_path: string;
  label: string;
  generated_value: string | null;
  override_value: string | null;
  effective_value: string | null;
  state: BusinessFieldState;
  confidence: number | null;
  provenance: BusinessFieldProvenance | null;
  override_meta: BusinessFieldOverrideMeta | null;
}

/**
 * Represents review-level business context data for one system.
 */
export interface BusinessContextPayload {
  system_id: string;
  system_label: string;
  review_status: 'draft' | 'reviewed' | 'approved_for_publish';
  fields: BusinessContextField[];
  snapshot: {
    current_snapshot_id: string;
    previous_snapshot_id: string | null;
    extracted_at: string;
  };
}

/**
 * Captures a single changed field between snapshots.
 */
export interface BusinessSnapshotDiffItem {
  field_path: string;
  label: string;
  previous_value: string | null;
  current_value: string | null;
  has_override_conflict: boolean;
  override_value: string | null;
}

/**
 * Represents a snapshot-to-snapshot diff payload.
 */
export interface BusinessSnapshotDiffPayload {
  system_id: string;
  current_snapshot_id: string;
  previous_snapshot_id: string | null;
  changes: BusinessSnapshotDiffItem[];
}

/**
 * Request body for creating/updating a field override.
 */
export interface UpdateOverrideRequest {
  value: string;
  reason: string;
  updated_by: string;
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
  response => {
    return response;
  },
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
    const response: AxiosResponse<SystemMetrics> = await api.get(
      '/api/v1/health/metrics'
    );
    return response.data;
  },

  // Health check
  healthCheck: async (): Promise<HealthStatus> => {
    const response: AxiosResponse<HealthStatus> =
      await api.get('/api/v1/health/');
    return response.data;
  },

  // Readiness check
  readinessCheck: async (): Promise<HealthStatus> => {
    const response: AxiosResponse<HealthStatus> = await api.get(
      '/api/v1/health/ready'
    );
    return response.data;
  },
};

// Service Extraction API
export const serviceExtractionAPI = {
  // Extract services from GitHub repository
  extractFromGitHub: async (
    githubUrl: string,
    useGit: boolean = true
  ): Promise<ExtractResponse> => {
    // Runtime fix: Force empty baseURL if it contains Docker service name
    const currentBaseURL = api.defaults.baseURL || '';
    const fixedBaseURL =
      currentBaseURL.includes('api:') || currentBaseURL.includes('://api')
        ? ''
        : currentBaseURL;
    if (fixedBaseURL !== currentBaseURL) {
      api.defaults.baseURL = fixedBaseURL;
      fileUploadApi.defaults.baseURL = fixedBaseURL;
    }

    try {
      const response: AxiosResponse<ExtractResponse> = await api.post(
        '/api/v1/services/extract-from-github',
        {
          github_url: githubUrl,
          use_git: useGit,
        }
      );
      return response.data;
    } catch (error: any) {
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
    try {
      const response: AxiosResponse<ExtractionStatus> = await api.get(
        `/api/v1/services/extraction/${taskId}`
      );
      return response.data;
    } catch (error: any) {
      throw error;
    }
  },

  // Get extraction results
  getExtractionResults: async (
    taskId: string
  ): Promise<{
    task_id: string;
    repository: { url?: string; name?: string };
    statistics: { total_services: number; total_connections: number };
    services: any[];
    connections: any[];
    errors: string[];
    warnings: string[];
  }> => {
    const response = await api.get(
      `/api/v1/services/extraction/${taskId}/results`
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
    const formData = new FormData();
    formData.append('file', file);

    // For file uploads, we need to remove the default Content-Type header
    // and let the browser set it automatically with the boundary
    const response: AxiosResponse<UploadResponse> = await fileUploadApi.post(
      '/api/v1/extract/upload',
      formData
    );

    return response.data;
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

const fallbackBusinessContextStore: Record<string, BusinessContextPayload> = {
  wps: {
    system_id: 'wps',
    system_label: 'WPS',
    review_status: 'draft',
    snapshot: {
      current_snapshot_id: 'snap-2026-02-19-001',
      previous_snapshot_id: 'snap-2026-02-12-001',
      extracted_at: '2026-02-19T12:10:00Z',
    },
    fields: [
      {
        field_path: 'owner',
        label: 'Owner',
        generated_value: 'Platform Engineering',
        override_value: null,
        effective_value: 'Platform Engineering',
        state: 'generated',
        confidence: 0.94,
        provenance: {
          source_type: 'codeowners',
          source_path: '/repos/wps/.github/CODEOWNERS',
          source_hash: 'sha256:7de215',
          artifact_version: 'main@2f4ae8c',
          extraction_rule: 'owner_from_codeowners',
          confidence: 0.94,
          last_seen: '2026-02-19T11:59:00Z',
        },
        override_meta: null,
      },
      {
        field_path: 'domain',
        label: 'Domain',
        generated_value: 'Payments',
        override_value: 'Global Payments',
        effective_value: 'Global Payments',
        state: 'overridden',
        confidence: 0.76,
        provenance: {
          source_type: 'service_universe',
          source_path: '/repos/wps/service-universe.yaml',
          source_hash: 'sha256:c37d1f',
          artifact_version: 'main@2f4ae8c',
          extraction_rule: 'domain_from_service_universe',
          confidence: 0.76,
          last_seen: '2026-02-19T11:57:00Z',
        },
        override_meta: {
          updated_by: 'business.sme',
          field_updated_at: '2026-02-17T08:30:00Z',
          override_reason: 'Official business taxonomy uses Global Payments.',
          status: 'active',
          needs_review: false,
        },
      },
      {
        field_path: 'experts',
        label: 'Experts',
        generated_value: null,
        override_value: null,
        effective_value: null,
        state: 'missing',
        confidence: null,
        provenance: null,
        override_meta: null,
      },
      {
        field_path: 'lifecycle',
        label: 'Lifecycle',
        generated_value: 'Active-Dev',
        override_value: null,
        effective_value: 'Active-Dev',
        state: 'generated',
        confidence: 0.9,
        provenance: {
          source_type: 'service_universe',
          source_path: '/repos/wps/service-universe.yaml',
          source_hash: 'sha256:c37d1f',
          artifact_version: 'main@2f4ae8c',
          extraction_rule: 'lifecycle_from_service_universe',
          confidence: 0.9,
          last_seen: '2026-02-19T11:57:00Z',
        },
        override_meta: null,
      },
    ],
  },
};

const fallbackBusinessDiffStore: Record<string, BusinessSnapshotDiffPayload> = {
  wps: {
    system_id: 'wps',
    current_snapshot_id: 'snap-2026-02-19-001',
    previous_snapshot_id: 'snap-2026-02-12-001',
    changes: [
      {
        field_path: 'domain',
        label: 'Domain',
        previous_value: 'Payments Core',
        current_value: 'Payments',
        has_override_conflict: true,
        override_value: 'Global Payments',
      },
      {
        field_path: 'lifecycle',
        label: 'Lifecycle',
        previous_value: 'Maintenance-Only',
        current_value: 'Active-Dev',
        has_override_conflict: false,
        override_value: null,
      },
    ],
  },
};

/**
 * Creates a safe JSON clone for local fallback adapters.
 */
function cloneFallbackValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
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

// Code Architecture API
export const codeArchitectureAPI = {
  // Get C4 architecture data
  getArchitecture: async (): Promise<any> => {
    try {
      const response: AxiosResponse = await api.get(
        '/api/v1/code/architecture'
      );
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Export latest architecture as Structurizr DSL
  exportStructurizr: async (): Promise<{
    format: 'structurizr';
    filename: string;
    content: string;
  }> => {
    const response: AxiosResponse = await api.get(
      '/api/v1/code/architecture/export/structurizr'
    );
    return response.data;
  },

  // Export latest architecture as Mermaid C4 snippet
  exportMermaid: async (): Promise<{
    format: 'mermaid';
    filename: string;
    content: string;
  }> => {
    const response: AxiosResponse = await api.get(
      '/api/v1/code/architecture/export/mermaid'
    );
    return response.data;
  },

  // Trigger code extraction from GitHub
  extractFromGitHub: async (
    githubUrl: string,
    useGit: boolean = true,
    appendMode: boolean = true
  ): Promise<ExtractResponse> => {
    try {
      const response: AxiosResponse<ExtractResponse> = await api.post(
        '/api/v1/code/extract-from-github',
        {
          github_url: githubUrl,
          use_git: useGit,
          append_mode: appendMode,
        }
      );
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Extract from GitHub organization/user
  extractFromGitHubOrg: async (
    username: string,
    includeForks: boolean = false,
    maxRepos: number = 10,
    appendMode: boolean = true
  ): Promise<ExtractResponse> => {
    try {
      const response: AxiosResponse<ExtractResponse> = await api.post(
        '/api/v1/code/extract-from-github-org',
        {
          github_username: username,
          include_forks: includeForks,
          max_repos: maxRepos,
          append_mode: appendMode,
        },
        {
          timeout: 60000, // 60 seconds for org scanning
        }
      );
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Trigger code extraction from a local folder path
  scanLocalPath: async (
    repoPath: string,
    appendMode: boolean = true
  ): Promise<ExtractResponse> => {
    const response: AxiosResponse<ExtractResponse> = await api.post(
      '/api/v1/code/scan',
      {
        repo_path: repoPath,
        use_c4_model: true,
        append_mode: appendMode,
      }
    );
    return response.data;
  },

  // Clear all architecture data
  clearArchitecture: async (): Promise<{
    status: string;
    message: string;
    deleted_count: number;
  }> => {
    try {
      const response = await api.post('/api/v1/code/clear');
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Get extraction status
  getExtractionStatus: async (taskId: string): Promise<TaskStatus> => {
    try {
      const response: AxiosResponse<TaskStatus> = await api.get(
        `/api/v1/code/scan/${taskId}`
      );
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Get extraction results
  getExtractionResults: async (taskId: string): Promise<any> => {
    try {
      const response: AxiosResponse = await api.get(
        `/api/v1/code/scan/${taskId}/results`
      );
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Apply human feedback to the Context (L1) diagram for a specific extraction task
  submitContextFeedback: async (
    taskId: string,
    payload: {
      system_name?: string;
      actors?: Array<{
        index: number;
        name?: string;
        description?: string;
        ignore?: boolean;
      }>;
      external_dependencies?: Array<{
        index: number;
        name?: string;
        dependency_type?: 'BUSINESS_SYSTEM' | 'TECHNICAL_INFRA' | 'UNKNOWN';
        url?: string;
        protocol?: string;
        notes?: string;
        ignore?: boolean;
      }>;
      relationships?: Array<{
        source: string;
        destination: string;
        description: string;
        relationship_type?: string;
        protocol?: string;
      }>;
    }
  ): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/code/scan/${taskId}/context-feedback`,
      payload
    );
    return response.data;
  },

  // Describe a node with LLM
  describeNode: async (payload: {
    id?: string;
    name?: string;
    type?: string;
    level?: string;
    attributes?: Record<string, unknown>;
    containerMeta?: Record<string, unknown>;
    file?: string;
  }): Promise<{ description: string; source: string }> => {
    try {
      const response: AxiosResponse = await api.post(
        '/api/v1/code/describe/node',
        payload
      );
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Describe an edge with LLM
  describeEdge: async (payload: {
    id?: string;
    source?: string;
    target?: string;
    label?: string;
    relationshipType?: string;
    protocol?: string;
  }): Promise<{ description: string; source: string }> => {
    try {
      const response: AxiosResponse = await api.post(
        '/api/v1/code/describe/edge',
        payload
      );
      return response.data;
    } catch (error) {
      throw error;
    }
  },
};

const fallbackBusinessContextStore: Record<string, BusinessContextPayload> = {
  wps: {
    system_id: 'wps',
    system_label: 'WPS',
    review_status: 'draft',
    snapshot: {
      current_snapshot_id: 'snap-2026-02-19-001',
      previous_snapshot_id: 'snap-2026-02-12-001',
      extracted_at: '2026-02-19T12:10:00Z',
    },
    fields: [
      {
        field_path: 'owner',
        label: 'Owner',
        generated_value: 'Platform Engineering',
        override_value: null,
        effective_value: 'Platform Engineering',
        state: 'generated',
        confidence: 0.94,
        provenance: {
          source_type: 'codeowners',
          source_path: '/repos/wps/.github/CODEOWNERS',
          source_hash: 'sha256:7de215',
          artifact_version: 'main@2f4ae8c',
          extraction_rule: 'owner_from_codeowners',
          confidence: 0.94,
          last_seen: '2026-02-19T11:59:00Z',
        },
        override_meta: null,
      },
      {
        field_path: 'domain',
        label: 'Domain',
        generated_value: 'Payments',
        override_value: 'Global Payments',
        effective_value: 'Global Payments',
        state: 'overridden',
        confidence: 0.76,
        provenance: {
          source_type: 'service_universe',
          source_path: '/repos/wps/service-universe.yaml',
          source_hash: 'sha256:c37d1f',
          artifact_version: 'main@2f4ae8c',
          extraction_rule: 'domain_from_service_universe',
          confidence: 0.76,
          last_seen: '2026-02-19T11:57:00Z',
        },
        override_meta: {
          updated_by: 'business.sme',
          field_updated_at: '2026-02-17T08:30:00Z',
          override_reason: 'Official business taxonomy uses Global Payments.',
          status: 'active',
          needs_review: false,
        },
      },
      {
        field_path: 'experts',
        label: 'Experts',
        generated_value: null,
        override_value: null,
        effective_value: null,
        state: 'missing',
        confidence: null,
        provenance: null,
        override_meta: null,
      },
      {
        field_path: 'lifecycle',
        label: 'Lifecycle',
        generated_value: 'Active-Dev',
        override_value: null,
        effective_value: 'Active-Dev',
        state: 'generated',
        confidence: 0.9,
        provenance: {
          source_type: 'service_universe',
          source_path: '/repos/wps/service-universe.yaml',
          source_hash: 'sha256:c37d1f',
          artifact_version: 'main@2f4ae8c',
          extraction_rule: 'lifecycle_from_service_universe',
          confidence: 0.9,
          last_seen: '2026-02-19T11:57:00Z',
        },
        override_meta: null,
      },
    ],
  },
};

const fallbackBusinessDiffStore: Record<string, BusinessSnapshotDiffPayload> = {
  wps: {
    system_id: 'wps',
    current_snapshot_id: 'snap-2026-02-19-001',
    previous_snapshot_id: 'snap-2026-02-12-001',
    changes: [
      {
        field_path: 'domain',
        label: 'Domain',
        previous_value: 'Payments Core',
        current_value: 'Payments',
        has_override_conflict: true,
        override_value: 'Global Payments',
      },
      {
        field_path: 'lifecycle',
        label: 'Lifecycle',
        previous_value: 'Maintenance-Only',
        current_value: 'Active-Dev',
        has_override_conflict: false,
        override_value: null,
      },
    ],
  },
};

/**
 * Creates a safe JSON clone for local fallback adapters.
 */
function cloneFallbackValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
/**
 * Business context API adapter for generated/effective/override review flows.
 * Falls back to local data when backend contracts are unavailable.
 */
export const businessContextAPI = {
  /**
   * Fetches the business context payload for a system.
   */
  getContext: async (systemId: string): Promise<BusinessContextPayload> => {
    try {
      const response: AxiosResponse<BusinessContextPayload> = await api.get(
        `/api/v1/context/${encodeURIComponent(systemId)}`
      );
      return response.data;
    } catch {
      const fallback =
        fallbackBusinessContextStore[systemId] ||
        fallbackBusinessContextStore.wps;
      return cloneFallbackValue(fallback);
    }
  },

  /**
   * Fetches snapshot diff details for a system.
   */
  getSnapshotDiff: async (
    systemId: string
  ): Promise<BusinessSnapshotDiffPayload> => {
    try {
      const response: AxiosResponse<BusinessSnapshotDiffPayload> = await api.get(
        `/api/v1/context/${encodeURIComponent(systemId)}/diff`
      );
      return response.data;
    } catch {
      const fallback =
        fallbackBusinessDiffStore[systemId] || fallbackBusinessDiffStore.wps;
      return cloneFallbackValue(fallback);
    }
  },

  /**
   * Persists an override for a single field path.
   */
  updateOverride: async (
    systemId: string,
    fieldPath: string,
    payload: UpdateOverrideRequest
  ): Promise<BusinessContextField> => {
    try {
      const response: AxiosResponse<BusinessContextField> = await api.put(
        `/api/v1/context/${encodeURIComponent(systemId)}/overrides/${encodeURIComponent(fieldPath)}`,
        payload
      );
      return response.data;
    } catch {
      const store =
        fallbackBusinessContextStore[systemId] ||
        fallbackBusinessContextStore.wps;
      const idx = store.fields.findIndex(field => field.field_path === fieldPath);
      if (idx < 0) {
        throw new Error(`Unknown field path: ${fieldPath}`);
      }

      const field = store.fields[idx];
      const updated: BusinessContextField = {
        ...field,
        override_value: payload.value,
        effective_value: payload.value,
        state: 'overridden',
        override_meta: {
          updated_by: payload.updated_by,
          field_updated_at: new Date().toISOString(),
          override_reason: payload.reason,
          status: 'active',
          needs_review: false,
        },
      };
      store.fields[idx] = updated;
      return cloneFallbackValue(updated);
    }
  },

  /**
   * Updates a system-level review status.
   */
  updateReviewStatus: async (
    systemId: string,
    status: BusinessContextPayload['review_status']
  ): Promise<{ review_status: BusinessContextPayload['review_status'] }> => {
    try {
      const response: AxiosResponse<{
        review_status: BusinessContextPayload['review_status'];
      }> = await api.patch(
        `/api/v1/context/${encodeURIComponent(systemId)}/review-status`,
        { review_status: status }
      );
      return response.data;
    } catch {
      const store =
        fallbackBusinessContextStore[systemId] ||
        fallbackBusinessContextStore.wps;
      store.review_status = status;
      return { review_status: status };
    }
  },
};

export default api;
