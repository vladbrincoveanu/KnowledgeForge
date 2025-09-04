// Common TypeScript interfaces and types for the application
import React from 'react';

// Base entity interfaces
export interface Entity {
  id?: string;
  name: string;
  entity_type: string;
  confidence: number;
  source_columns?: string[];
  source_value?: string;
  attributes?: Record<string, any>;
}

export interface Relationship {
  id?: string;
  source_entity_id?: string;
  target_entity_id?: string;
  relationship_type: string;
  confidence: number;
  source_columns?: string[];
  attributes?: Record<string, any>;
}

// Task and status interfaces
export interface TaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  message?: string;
  error?: string;
  result?: Record<string, unknown>;
}

// Metrics and health interfaces
export interface SystemMetrics {
  system_metrics?: {
    total_tasks: number;
    completed_tasks: number;
    failed_tasks: number;
    success_rate: number;
  };
  extraction_metrics?: {
    average_processing_time: number;
    total_entities_extracted: number;
    total_relationships_discovered: number;
  };
  quality_metrics?: {
    average_entity_confidence: number;
    average_relationship_confidence: number;
    data_coverage: number;
  };
  timestamp: string;
}

export interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  version?: string;
  timestamp: string;
  dependencies?: Record<string, boolean>;
}

// Graph and visualization interfaces
export interface GraphNode {
  id: string;
  label: string;
  type: string;
  entityType?: string;
  confidence?: number;
  x?: number;
  y?: number;
  metadata?: {
    columns?: number;
    uploadDate?: string;
    [key: string]: unknown;
  };
  columns?: Record<string, unknown>;
}

export interface GraphLink {
  id: string;
  source: string;
  target: string;
  label: string;
  confidence?: number;
  source_collection?: string;
  target_collection?: string;
  source_column?: string;
  target_column?: string;
  columnA?: string;
  columnB?: string;
  confidence_score?: number;
  llm_analysis?: LLMAnalysis;
  connection_type?: string;
  type?: string;
  created_at?: string;
  createdAt?: string;
  merged_metadata?: unknown;
  mergedMetadata?: unknown;
  join_strategy?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

// Query builder interfaces
export interface QueryNode {
  id: string;
  name: string;
  node_type: 'table' | 'field' | 'join' | 'filter' | 'aggregate';
  position: { x: number; y: number };
  properties: Record<string, string | number | boolean>;
  metadata?: Record<string, string | number | boolean>;
  created_at: string;
  updated_at: string;
}

export interface QueryEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: 'select' | 'join' | 'filter' | 'group' | 'order';
  properties: Record<string, string | number | boolean>;
  conditions?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SemanticQuery {
  id: string;
  name: string;
  description: string;
  nodes: QueryNode[];
  edges: QueryEdge[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// Node and edge type definitions
export interface NodeType {
  type: string;
  label: string;
  icon: string;
  description: string;
}

export interface EdgeType {
  type: string;
  label: string;
  description: string;
}

// Insight interface
export interface Insight {
  insight_type: string;
  description: string;
  confidence_score: number;
  recommendations: string[];
}

// Pagination interface
export interface Pagination {
  page: number;
  limit: number;
  total: number;
}

export interface PaginationState {
  entities: Pagination;
  relationships: Pagination;
}

// Feedback interface
export interface FeedbackForm {
  entity_id?: string;
  relationship_id?: string;
  feedback_type: string;
  feedback_value: string;
  confidence_delta: number;
  user_id: string;
}

// File upload interfaces
export interface UploadedFile {
  name: string;
  headers: string[];
  data: Record<string, string>[];
  size: number;
  rowCount: number;
  type: string;
}

// LLM Analysis interface
export interface LLMAnalysis {
  reasoning: string;
  business_context: string;
  connection_type?: string;
  suggested_join_strategy?: string;
  potential_issues?: string[];
  recommendations?: string[];
  confidence_level?: 'High' | 'Medium' | 'Low';
}

// Connection interface
export interface Connection {
  id?: string;
  fileA: string;
  fileB: string;
  columnA: string;
  columnB: string;
  confidence: number;
  confidence_score?: number;
  ai_score?: number;
  source_collection?: string;
  target_collection?: string;
  source_column?: string;
  target_column?: string;
  connection_type?: string;
  llmAnalysis?: LLMAnalysis;
  llm_analysis?: LLMAnalysis;
}

// Chart data interfaces
export interface ChartData {
  name: string;
  value: number;
  color?: string;
  unit?: string;
}

// API response types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// Feedback response type
export interface FeedbackResponse {
  success: boolean;
  message?: string;
}

// Axios error response type
export interface AxiosErrorResponse {
  response?: {
    status: number;
    statusText: string;
    data: unknown;
    headers: Record<string, string>;
  };
  message: string;
}

// Event handler types
export type MouseEventHandler = (event: React.MouseEvent) => void;
export type ChangeEventHandler = (
  event: React.ChangeEvent<
    HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
  >
) => void;
export type FormEventHandler = (event: React.FormEvent) => void;
export type KeyboardEventHandler = (event: React.KeyboardEvent) => void;
