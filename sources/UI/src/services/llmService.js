/**
 * LLM Service for Ollama Integration
 * Provides AI analysis for data connections using local Ollama models
 */

class LLMService {
  constructor() {
    this.ollamaUrl = process.env.REACT_APP_OLLAMA_URL || 'http://localhost:11434';
    this.model = process.env.REACT_APP_OLLAMA_MODEL || 'llama2';
    this.disableOllama = String(process.env.REACT_APP_OLLAMA_DISABLED || '').toLowerCase() === 'true';
    this.ollamaAvailable = null; // tri-state: null = unknown, true/false = known
    this.warnedUnavailable = false;
  }

  /**
   * Analyze potential connections between datasets - COMPLETELY REWRITTEN
   */
  async analyzeConnections(connections, maxConnections = 5) {
    try {
      console.log(`Smart analyzing ${connections.length} connections with Ollama...`);
      
      // First, pre-filter connections using smart rules
      const preFiltered = this.preFilterConnections(connections);
      console.log(`Pre-filtered to ${preFiltered.length} connections`);
      
      // Take only the top connections for LLM analysis
      const topConnections = preFiltered.slice(0, maxConnections);
      
      // If Ollama is disabled or unavailable, use fallback analyses without attempting fetches
      const canUseOllama = await this.ensureOllamaAvailable();
      if (!canUseOllama) {
        if (!this.warnedUnavailable) {
          console.warn('Ollama is disabled or not reachable. Using fallback analysis.');
          this.warnedUnavailable = true;
        }
        const analyses = topConnections.map((connection) => this.getFallbackAnalysis(connection));
        const scoredConnections = topConnections.map((connection, index) => ({
          ...connection,
          llm_analysis: analyses[index],
          ai_score: this.calculateAIScore(analyses[index])
        }));
        const rankedConnections = scoredConnections
          .sort((a, b) => b.ai_score - a.ai_score)
          .slice(0, maxConnections);
        console.log(`Returning top ${rankedConnections.length} smart connections (fallback)`);
        return rankedConnections;
      }

      // Create analysis prompts for each connection
      const analysisPromises = topConnections.map(connection => 
        this.analyzeSingleConnection(connection)
      );
      
      // Run all analyses in parallel
      const analyses = await Promise.all(analysisPromises);
      
      // Score and rank connections
      const scoredConnections = topConnections.map((connection, index) => ({
        ...connection,
        llm_analysis: analyses[index],
        ai_score: this.calculateAIScore(analyses[index])
      }));
      
      // Sort by AI score and return top connections
      const rankedConnections = scoredConnections
        .sort((a, b) => b.ai_score - a.ai_score)
        .slice(0, maxConnections);
      
      console.log(`Returning top ${rankedConnections.length} smart connections`);
      return rankedConnections;
      
    } catch (error) {
      console.error('Error analyzing connections with Ollama:', error);
      // Fallback to smart pre-filtered connections without AI analysis
      return this.preFilterConnections(connections).slice(0, maxConnections);
    }
  }

  /**
   * Analyze a single connection using Ollama
   */
  async analyzeSingleConnection(connection) {
    const prompt = this.buildAnalysisPrompt(connection);
    
    try {
      // If Ollama unavailable, short-circuit to fallback without attempting fetch
      const canUseOllama = await this.ensureOllamaAvailable();
      if (!canUseOllama) {
        return this.getFallbackAnalysis(connection);
      }

      const response = await fetch(`${this.ollamaUrl}/api/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: this.model,
          prompt: prompt,
          stream: false,
          options: {
            temperature: 0.3,
            top_p: 0.9,
            max_tokens: 500
          }
        })
      });

      if (!response.ok) {
        throw new Error(`Ollama API error: ${response.status}`);
      }

      const data = await response.json();
      const analysis = this.parseLLMResponse(data.response);
      
      return analysis;
      
    } catch (error) {
      console.error('Error calling Ollama:', error);
      return this.getFallbackAnalysis(connection);
    }
  }

  /**
   * Build analysis prompt for Ollama
   */
  buildAnalysisPrompt(connection) {
    return `Analyze this potential data connection and provide insights:

DATASET A: ${connection.source_collection}
Column: ${connection.source_column}

DATASET B: ${connection.target_collection}
Column: ${connection.target_column}

Connection Type: ${connection.connection_type || 'unknown'}
Confidence Score: ${connection.confidence_score || 0}

Please analyze this connection and provide:

1. REASONING: Why these columns might be related
2. BUSINESS_CONTEXT: How this connection could be useful
3. CONNECTION_TYPE: Most likely relationship type (foreign_key, lookup, etc.)
4. SUGGESTED_JOIN_STRATEGY: Recommended join approach
5. POTENTIAL_ISSUES: List any data quality or technical concerns
6. RECOMMENDATIONS: Best practices for implementing this connection
7. CONFIDENCE_LEVEL: High/Medium/Low based on your analysis

Format your response as JSON:
{
  "reasoning": "...",
  "business_context": "...",
  "connection_type": "...",
  "suggested_join_strategy": "...",
  "potential_issues": ["issue1", "issue2"],
  "recommendations": ["rec1", "rec2"],
  "confidence_level": "High/Medium/Low"
}`;
  }

  /**
   * Parse LLM response into structured format
   */
  parseLLMResponse(response) {
    try {
      // Try to extract JSON from response
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        return {
          reasoning: parsed.reasoning || 'AI analysis not available',
          business_context: parsed.business_context || 'Context not available',
          connection_type: parsed.connection_type || 'unknown',
          suggested_join_strategy: parsed.suggested_join_strategy || 'inner_join',
          potential_issues: parsed.potential_issues || [],
          recommendations: parsed.recommendations || [],
          confidence_level: parsed.confidence_level || 'Medium'
        };
      }
    } catch (error) {
      console.error('Error parsing LLM response:', error);
    }
    
    // Fallback parsing for non-JSON responses
    return this.parseTextResponse(response);
  }

  /**
   * Parse text response when JSON parsing fails
   */
  parseTextResponse(response) {
    const analysis = {
      reasoning: 'AI analysis completed',
      business_context: 'Connection analysis provided',
      connection_type: 'foreign_key',
      suggested_join_strategy: 'inner_join',
      potential_issues: ['Data validation recommended'],
      recommendations: ['Verify data types before joining'],
      confidence_level: 'Medium'
    };

    // Extract insights from text response
    if (response.includes('foreign key') || response.includes('foreign_key')) {
      analysis.connection_type = 'foreign_key';
    }
    if (response.includes('lookup') || response.includes('reference')) {
      analysis.connection_type = 'lookup';
    }
    if (response.includes('high') || response.includes('strong')) {
      analysis.confidence_level = 'High';
    }
    if (response.includes('low') || response.includes('weak')) {
      analysis.confidence_level = 'Low';
    }

    return analysis;
  }

  /**
   * Calculate AI score based on analysis
   */
  calculateAIScore(analysis) {
    let score = 0.5; // Base score
    
    // Adjust based on confidence level
    switch (analysis.confidence_level?.toLowerCase()) {
      case 'high':
        score += 0.3;
        break;
      case 'medium':
        score += 0.1;
        break;
      case 'low':
        score -= 0.2;
        break;
    }
    
    // Adjust based on connection type
    if (analysis.connection_type === 'foreign_key') {
      score += 0.2;
    } else if (analysis.connection_type === 'lookup') {
      score += 0.1;
    }
    
    // Adjust based on issues (fewer issues = higher score)
    const issuePenalty = analysis.potential_issues?.length * 0.05 || 0;
    score -= issuePenalty;
    
    // Ensure score is between 0 and 1
    return Math.max(0, Math.min(1, score));
  }

  /**
   * Fallback analysis when Ollama is not available
   */
  getFallbackAnalysis(connection) {
    return {
      reasoning: 'Connection analysis using fallback logic',
      business_context: 'Standard data relationship analysis',
      connection_type: connection.connection_type || 'foreign_key',
      suggested_join_strategy: 'inner_join',
      potential_issues: ['Data validation recommended'],
      recommendations: ['Verify data types and referential integrity'],
      confidence_level: 'Medium'
    };
  }

  /**
   * Pre-filter connections using smart rules - NO MORE RANDOM CONNECTIONS!
   */
  preFilterConnections(connections) {
    console.log('Pre-filtering connections with smart rules...');
    
    const filtered = connections.filter(connection => {
      const sourceCol = connection.source_column?.toLowerCase() || '';
      const targetCol = connection.target_column?.toLowerCase() || '';
      const sourceCollection = connection.source_collection?.toLowerCase() || '';
      const targetCollection = connection.target_collection?.toLowerCase() || '';
      
      // Rule 1: Exact name matches (highest priority)
      if (sourceCol === targetCol) {
        return true;
      }
      
      // Rule 2: Common identifier patterns
      const idPatterns = ['id', 'key', 'code', 'ref', 'num', 'no'];
      for (const pattern of idPatterns) {
        if (sourceCol.includes(pattern) && targetCol.includes(pattern)) {
          // Check if they're related (e.g., customer_id and customer_id)
          const sourceBase = sourceCol.replace(pattern, '').replace(/[_-]/g, '');
          const targetBase = targetCol.replace(pattern, '').replace(/[_-]/g, '');
          if (sourceBase && targetBase && (sourceBase.includes(targetBase) || targetBase.includes(sourceBase))) {
            return true;
          }
        }
      }
      
      // Rule 3: Semantic matches (e.g., customer_name vs client_name)
      const semanticPairs = [
        ['customer', 'client'], ['user', 'customer'], ['user', 'client'],
        ['order', 'purchase'], ['sale', 'order'], ['transaction', 'order'],
        ['product', 'item'], ['goods', 'product'], ['service', 'product'],
        ['date', 'created'], ['date', 'timestamp'], ['time', 'date'],
        ['email', 'mail'], ['phone', 'telephone'], ['mobile', 'phone'],
        ['name', 'title'], ['description', 'details'], ['price', 'cost'],
        ['quantity', 'amount'], ['total', 'sum'], ['address', 'location']
      ];
      
      for (const [word1, word2] of semanticPairs) {
        if ((sourceCol.includes(word1) && targetCol.includes(word2)) ||
            (sourceCol.includes(word2) && targetCol.includes(word1))) {
          return true;
        }
      }
      
      // Rule 4: Collection name similarity (e.g., customers.csv and customer_orders.csv)
      if (sourceCollection && targetCollection) {
        const sourceWords = sourceCollection.split(/[_\s-]/);
        const targetWords = targetCollection.split(/[_\s-]/);
        const commonWords = sourceWords.filter(word => targetWords.includes(word));
        if (commonWords.length > 0 && (sourceCol.includes(commonWords[0]) || targetCol.includes(commonWords[0]))) {
          return true;
        }
      }
      
      // Rule 5: High confidence connections (above 0.8)
      if (connection.confidence_score >= 0.8) {
        return true;
      }
      
      // Reject everything else - NO MORE RANDOM CONNECTIONS!
      return false;
    });
    
    console.log(`Filtered from ${connections.length} to ${filtered.length} logical connections`);
    return filtered;
  }

  /**
   * Check if Ollama is available
   */
  async checkOllamaStatus() {
    try {
      const response = await fetch(`${this.ollamaUrl}/api/tags`);
      return response.ok;
    } catch (error) {
      console.error('Ollama not available:', error);
      return false;
    }
  }

  /**
   * Determine whether Ollama can be used (cached per session)
   */
  async ensureOllamaAvailable() {
    if (this.disableOllama) {
      this.ollamaAvailable = false;
      return false;
    }
    if (this.ollamaAvailable === null) {
      this.ollamaAvailable = await this.checkOllamaStatus();
    }
    return this.ollamaAvailable;
  }

  /**
   * Get available models
   */
  async getAvailableModels() {
    try {
      const response = await fetch(`${this.ollamaUrl}/api/tags`);
      if (response.ok) {
        const data = await response.json();
        return data.models || [];
      }
    } catch (error) {
      console.error('Error fetching models:', error);
    }
    return [];
  }
}

export default new LLMService(); 