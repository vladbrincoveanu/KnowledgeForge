// TypeScript interfaces
interface Position {
  x: number;
  y: number;
}

interface QueryNode {
  id: string;
  name: string;
  node_type: 'table' | 'field' | 'join' | 'filter' | 'aggregate';
  position: Position;
  properties: Record<string, any>;
  created_at: string;
  updated_at: string;
}

interface QueryEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: 'select' | 'join' | 'filter' | 'group' | 'order';
  properties: Record<string, any>;
  created_at: string;
  updated_at: string;
}

interface SemanticQuery {
  id: string;
  name: string;
  description: string;
  metadata?: Record<string, any>;
  nodes?: QueryNode[];
  edges?: QueryEdge[];
  created_at: string;
  updated_at: string;
}

interface QueryTemplate {
  id: string;
  name: string;
  description: string;
  nodes: QueryNode[];
  edges: QueryEdge[];
}

interface ExportFormat {
  id: string;
  name: string;
  description: string;
  file_extension: string;
}

interface NodeType {
  id: string;
  name: string;
  description: string;
  properties: string[];
}

interface EdgeType {
  id: string;
  name: string;
  description: string;
  properties: string[];
}

interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

interface ConnectionStatus {
  connected: boolean;
  message: string;
}

interface TranslationResult {
  natural_language: string;
  sql_query?: string;
  explanation: string;
}

interface InsightResult {
  insights: string[];
  recommendations: string[];
  complexity_score: number;
}

interface ExportResult {
  content: string;
  format: string;
  filename: string;
}

interface RequestOptions {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
}

class SemanticQueryService {
  private baseUrl: string;
  private apiPrefix: string;

  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
    this.apiPrefix = '/api/semantic-queries';
  }

  private async makeRequest<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${this.apiPrefix}${endpoint}`;

    const defaultOptions: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
      },
      ...options,
    };

    try {
      const response = await fetch(url, defaultOptions);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `HTTP error! status: ${response.status}`
        );
      }

      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // Query CRUD operations
  async createQuery(
    name: string,
    description: string,
    metadata: Record<string, any> = {}
  ): Promise<SemanticQuery> {
    const params = new URLSearchParams({
      name,
      description,
      ...(metadata && { metadata: JSON.stringify(metadata) }),
    });

    return this.makeRequest<SemanticQuery>(`/?${params.toString()}`, {
      method: 'POST',
    });
  }

  async getQueries(): Promise<SemanticQuery[]> {
    return this.makeRequest<SemanticQuery[]>('/');
  }

  async getQuery(queryId: string): Promise<SemanticQuery> {
    return this.makeRequest<SemanticQuery>(`/${queryId}`);
  }

  async deleteQuery(queryId: string): Promise<void> {
    await this.makeRequest<void>(`/${queryId}`, {
      method: 'DELETE',
    });
  }

  // Node operations
  async addNode(
    queryId: string,
    node: Omit<QueryNode, 'created_at' | 'updated_at'>
  ): Promise<QueryNode> {
    return this.makeRequest<QueryNode>(`/${queryId}/nodes`, {
      method: 'POST',
      body: JSON.stringify(node),
    });
  }

  async removeNode(queryId: string, nodeId: string): Promise<void> {
    await this.makeRequest<void>(`/${queryId}/nodes/${nodeId}`, {
      method: 'DELETE',
    });
  }

  // Edge operations
  async addEdge(
    queryId: string,
    edge: Omit<QueryEdge, 'created_at' | 'updated_at'>
  ): Promise<QueryEdge> {
    return this.makeRequest<QueryEdge>(`/${queryId}/edges`, {
      method: 'POST',
      body: JSON.stringify(edge),
    });
  }

  async removeEdge(queryId: string, edgeId: string): Promise<void> {
    await this.makeRequest<void>(`/${queryId}/edges/${edgeId}`, {
      method: 'DELETE',
    });
  }

  // AI-powered features
  async translateToNaturalLanguage(
    queryId: string
  ): Promise<TranslationResult> {
    return this.makeRequest<TranslationResult>(`/${queryId}/translate`, {
      method: 'POST',
    });
  }

  async generateInsights(queryId: string): Promise<InsightResult> {
    return this.makeRequest<InsightResult>(`/${queryId}/insights`, {
      method: 'POST',
    });
  }

  // Export functionality
  async exportQuery(
    queryId: string,
    exportFormat: string
  ): Promise<ExportResult> {
    const params = new URLSearchParams({
      export_format: exportFormat,
    });

    return this.makeRequest<ExportResult>(
      `/${queryId}/export?${params.toString()}`,
      {
        method: 'POST',
      }
    );
  }

  // Metadata endpoints
  async getExportFormats(): Promise<ExportFormat[]> {
    return this.makeRequest<ExportFormat[]>('/export-formats');
  }

  async getNodeTypes(): Promise<NodeType[]> {
    return this.makeRequest<NodeType[]>('/node-types');
  }

  async getEdgeTypes(): Promise<EdgeType[]> {
    return this.makeRequest<EdgeType[]>('/edge-types');
  }

  // Validation
  async validateQuery(queryId: string): Promise<ValidationResult> {
    return this.makeRequest<ValidationResult>(`/${queryId}/validate`, {
      method: 'POST',
    });
  }

  // Batch operations
  async updateQuery(
    queryId: string,
    updates: Partial<SemanticQuery>
  ): Promise<SemanticQuery> {
    // This would typically be a PUT/PATCH endpoint, but we'll simulate it
    // by getting the current query and then updating it
    const currentQuery = await this.getQuery(queryId);
    const updatedQuery = { ...currentQuery, ...updates };

    // In a real implementation, you'd have a PUT endpoint
    // For now, we'll return the updated query object
    return updatedQuery;
  }

  async saveQueryState(
    queryId: string,
    nodes: QueryNode[],
    edges: QueryEdge[]
  ): Promise<SemanticQuery> {
    // Save the current state of nodes and edges
    const query = await this.getQuery(queryId);

    // Update the query with new nodes and edges
    const updatedQuery: SemanticQuery = {
      ...query,
      nodes,
      edges,
      updated_at: new Date().toISOString(),
    };

    // In a real implementation, you'd have a PUT endpoint to save the entire query
    // For now, we'll simulate saving by returning the updated query
    return updatedQuery;
  }

  // Utility methods
  async testConnection(): Promise<ConnectionStatus> {
    try {
      await this.makeRequest<ExportFormat[]>('/export-formats');
      return {
        connected: true,
        message: 'Successfully connected to semantic query API',
      };
    } catch (error: any) {
      return {
        connected: false,
        message: `Connection failed: ${error.message}`,
      };
    }
  }

  // Local storage fallback for offline functionality
  saveToLocalStorage(key: string, data: any): boolean {
    try {
      localStorage.setItem(key, JSON.stringify(data));
      return true;
    } catch (error) {
      console.error('Failed to save to localStorage:', error);
      return false;
    }
  }

  loadFromLocalStorage<T>(key: string): T | null {
    try {
      const data = localStorage.getItem(key);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      console.error('Failed to load from localStorage:', error);
      return null;
    }
  }

  // Query templates for quick start
  getQueryTemplates(): QueryTemplate[] {
    const now = new Date().toISOString();

    return [
      {
        id: 'template_simple_select',
        name: 'Simple SELECT Query',
        description: 'Basic query to select fields from a table',
        nodes: [
          {
            id: 'node_table_1',
            name: 'customers',
            node_type: 'table',
            position: { x: 100, y: 100 },
            properties: {},
            created_at: now,
            updated_at: now,
          },
          {
            id: 'node_field_1',
            name: 'customer_id',
            node_type: 'field',
            position: { x: 300, y: 100 },
            properties: {},
            created_at: now,
            updated_at: now,
          },
          {
            id: 'node_field_2',
            name: 'customer_name',
            node_type: 'field',
            position: { x: 300, y: 150 },
            properties: {},
            created_at: now,
            updated_at: now,
          },
        ],
        edges: [
          {
            id: 'edge_select_1',
            source_node_id: 'node_table_1',
            target_node_id: 'node_field_1',
            edge_type: 'select',
            properties: {},
            created_at: now,
            updated_at: now,
          },
          {
            id: 'edge_select_2',
            source_node_id: 'node_table_1',
            target_node_id: 'node_field_2',
            edge_type: 'select',
            properties: {},
            created_at: now,
            updated_at: now,
          },
        ],
      },
      {
        id: 'template_join_query',
        name: 'JOIN Query',
        description: 'Query joining two tables with conditions',
        nodes: [
          {
            id: 'node_table_1',
            name: 'orders',
            node_type: 'table',
            position: { x: 100, y: 100 },
            properties: {},
            created_at: now,
            updated_at: now,
          },
          {
            id: 'node_table_2',
            name: 'customers',
            node_type: 'table',
            position: { x: 100, y: 250 },
            properties: {},
            created_at: now,
            updated_at: now,
          },
          {
            id: 'node_join_1',
            name: 'customer_id',
            node_type: 'join',
            position: { x: 300, y: 175 },
            properties: { join_type: 'INNER' },
            created_at: now,
            updated_at: now,
          },
          {
            id: 'node_field_1',
            name: 'order_id',
            node_type: 'field',
            position: { x: 500, y: 100 },
            properties: {},
            created_at: now,
            updated_at: now,
          },
          {
            id: 'node_field_2',
            name: 'customer_name',
            node_type: 'field',
            position: { x: 500, y: 150 },
            properties: {},
            created_at: now,
            updated_at: now,
          },
        ],
        edges: [
          {
            id: 'edge_join_1',
            source_node_id: 'node_table_1',
            target_node_id: 'node_join_1',
            edge_type: 'join',
            properties: {},
            created_at: now,
            updated_at: now,
          },
          {
            id: 'edge_join_2',
            source_node_id: 'node_table_2',
            target_node_id: 'node_join_1',
            edge_type: 'join',
            properties: {},
            created_at: now,
            updated_at: now,
          },
          {
            id: 'edge_select_1',
            source_node_id: 'node_join_1',
            target_node_id: 'node_field_1',
            edge_type: 'select',
            properties: {},
            created_at: now,
            updated_at: now,
          },
          {
            id: 'edge_select_2',
            source_node_id: 'node_join_1',
            target_node_id: 'node_field_2',
            edge_type: 'select',
            properties: {},
            created_at: now,
            updated_at: now,
          },
        ],
      },
    ];
  }

  // Import query from template
  async importFromTemplate(templateId: string): Promise<SemanticQuery> {
    const templates = this.getQueryTemplates();
    const template = templates.find(t => t.id === templateId);

    if (!template) {
      throw new Error(`Template ${templateId} not found`);
    }

    // Create a new query from the template
    const query = await this.createQuery(template.name, template.description, {
      template_source: templateId,
    });

    // Add nodes and edges from the template
    for (const node of template.nodes) {
      await this.addNode(query.id, node);
    }

    for (const edge of template.edges) {
      await this.addEdge(query.id, edge);
    }

    return query;
  }
}

export default SemanticQueryService;
