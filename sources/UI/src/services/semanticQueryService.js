class SemanticQueryService {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
    this.apiPrefix = '/api/semantic-queries';
  }

  async makeRequest(endpoint, options = {}) {
    const url = `${this.baseUrl}${this.apiPrefix}${endpoint}`;
    
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
      },
      ...options,
    };

    try {
      const response = await fetch(url, defaultOptions);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // Query CRUD operations
  async createQuery(name, description, metadata = {}) {
    const params = new URLSearchParams({
      name,
      description,
      ...(metadata && { metadata: JSON.stringify(metadata) })
    });
    
    return this.makeRequest(`/?${params.toString()}`, {
      method: 'POST'
    });
  }

  async getQueries() {
    return this.makeRequest('/');
  }

  async getQuery(queryId) {
    return this.makeRequest(`/${queryId}`);
  }

  async deleteQuery(queryId) {
    return this.makeRequest(`/${queryId}`, {
      method: 'DELETE'
    });
  }

  // Node operations
  async addNode(queryId, node) {
    return this.makeRequest(`/${queryId}/nodes`, {
      method: 'POST',
      body: JSON.stringify(node)
    });
  }

  async removeNode(queryId, nodeId) {
    return this.makeRequest(`/${queryId}/nodes/${nodeId}`, {
      method: 'DELETE'
    });
  }

  // Edge operations
  async addEdge(queryId, edge) {
    return this.makeRequest(`/${queryId}/edges`, {
      method: 'POST',
      body: JSON.stringify(edge)
    });
  }

  async removeEdge(queryId, edgeId) {
    return this.makeRequest(`/${queryId}/edges/${edgeId}`, {
      method: 'DELETE'
    });
  }

  // AI-powered features
  async translateToNaturalLanguage(queryId) {
    return this.makeRequest(`/${queryId}/translate`, {
      method: 'POST'
    });
  }

  async generateInsights(queryId) {
    return this.makeRequest(`/${queryId}/insights`, {
      method: 'POST'
    });
  }

  // Export functionality
  async exportQuery(queryId, exportFormat) {
    const params = new URLSearchParams({
      export_format: exportFormat
    });
    
    return this.makeRequest(`/${queryId}/export?${params.toString()}`, {
      method: 'POST'
    });
  }

  // Metadata endpoints
  async getExportFormats() {
    return this.makeRequest('/export-formats');
  }

  async getNodeTypes() {
    return this.makeRequest('/node-types');
  }

  async getEdgeTypes() {
    return this.makeRequest('/edge-types');
  }

  // Validation
  async validateQuery(queryId) {
    return this.makeRequest(`/${queryId}/validate`, {
      method: 'POST'
    });
  }

  // Batch operations
  async updateQuery(queryId, updates) {
    // This would typically be a PUT/PATCH endpoint, but we'll simulate it
    // by getting the current query and then updating it
    const currentQuery = await this.getQuery(queryId);
    const updatedQuery = { ...currentQuery, ...updates };
    
    // In a real implementation, you'd have a PUT endpoint
    // For now, we'll return the updated query object
    return updatedQuery;
  }

  async saveQueryState(queryId, nodes, edges) {
    // Save the current state of nodes and edges
    const query = await this.getQuery(queryId);
    
    // Update the query with new nodes and edges
    const updatedQuery = {
      ...query,
      nodes,
      edges,
      updated_at: new Date().toISOString()
    };
    
    // In a real implementation, you'd have a PUT endpoint to save the entire query
    // For now, we'll simulate saving by returning the updated query
    return updatedQuery;
  }

  // Utility methods
  async testConnection() {
    try {
      await this.makeRequest('/export-formats');
      return { connected: true, message: 'Successfully connected to semantic query API' };
    } catch (error) {
      return { connected: false, message: `Connection failed: ${error.message}` };
    }
  }

  // Local storage fallback for offline functionality
  saveToLocalStorage(key, data) {
    try {
      localStorage.setItem(key, JSON.stringify(data));
      return true;
    } catch (error) {
      console.error('Failed to save to localStorage:', error);
      return false;
    }
  }

  loadFromLocalStorage(key) {
    try {
      const data = localStorage.getItem(key);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      console.error('Failed to load from localStorage:', error);
      return null;
    }
  }

  // Query templates for quick start
  getQueryTemplates() {
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
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 'node_field_1',
            name: 'customer_id',
            node_type: 'field',
            position: { x: 300, y: 100 },
            properties: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 'node_field_2',
            name: 'customer_name',
            node_type: 'field',
            position: { x: 300, y: 150 },
            properties: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        ],
        edges: [
          {
            id: 'edge_select_1',
            source_node_id: 'node_table_1',
            target_node_id: 'node_field_1',
            edge_type: 'select',
            properties: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 'edge_select_2',
            source_node_id: 'node_table_1',
            target_node_id: 'node_field_2',
            edge_type: 'select',
            properties: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        ]
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
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 'node_table_2',
            name: 'customers',
            node_type: 'table',
            position: { x: 100, y: 250 },
            properties: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 'node_join_1',
            name: 'customer_id',
            node_type: 'join',
            position: { x: 300, y: 175 },
            properties: { join_type: 'INNER' },
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 'node_field_1',
            name: 'order_id',
            node_type: 'field',
            position: { x: 500, y: 100 },
            properties: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 'node_field_2',
            name: 'customer_name',
            node_type: 'field',
            position: { x: 500, y: 150 },
            properties: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        ],
        edges: [
          {
            id: 'edge_join_1',
            source_node_id: 'node_table_1',
            target_node_id: 'node_join_1',
            edge_type: 'join',
            properties: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 'edge_join_2',
            source_node_id: 'node_table_2',
            target_node_id: 'node_join_1',
            edge_type: 'join',
            properties: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 'edge_select_1',
            source_node_id: 'node_join_1',
            target_node_id: 'node_field_1',
            edge_type: 'select',
            properties: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 'edge_select_2',
            source_node_id: 'node_join_1',
            target_node_id: 'node_field_2',
            edge_type: 'select',
            properties: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        ]
      }
    ];
  }

  // Import query from template
  async importFromTemplate(templateId) {
    const templates = this.getQueryTemplates();
    const template = templates.find(t => t.id === templateId);
    
    if (!template) {
      throw new Error(`Template ${templateId} not found`);
    }
    
    // Create a new query from the template
    const query = await this.createQuery(
      template.name,
      template.description,
      { template_source: templateId }
    );
    
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
