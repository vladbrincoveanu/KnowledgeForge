from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import json

from ..domain.semantic_query_models import (
    SemanticQuery, QueryNode, QueryEdge, QueryNodeType, QueryEdgeType,
    ExportFormat, QueryTranslation, QueryExport, QueryInsight
)
from ..infrastructure.llm_analyzer import LLMAnalyzer


class SemanticQueryService:
    """Service for managing semantic queries and their operations"""
    
    def __init__(self, llm_analyzer: LLMAnalyzer):
        self.llm_analyzer = llm_analyzer
        self.queries: Dict[str, SemanticQuery] = {}
    
    def create_query(self, name: str, description: str, metadata: Dict[str, Any] = None) -> SemanticQuery:
        """Create a new semantic query"""
        query_id = str(uuid.uuid4())
        now = datetime.now()
        
        query = SemanticQuery(
            id=query_id,
            name=name,
            description=description,
            nodes=[],
            edges=[],
            metadata=metadata or {},
            created_at=now,
            updated_at=now
        )
        
        self.queries[query_id] = query
        return query
    
    def add_node(self, query_id: str, node: QueryNode) -> QueryNode:
        """Add a node to a semantic query"""
        if query_id not in self.queries:
            raise ValueError(f"Query {query_id} not found")
        
        # Ensure node has timestamps
        now = datetime.now()
        if not node.created_at:
            node.created_at = now
        node.updated_at = now
        
        self.queries[query_id].nodes.append(node)
        self.queries[query_id].updated_at = now
        
        return node
    
    def add_edge(self, query_id: str, edge: QueryEdge) -> QueryEdge:
        """Add an edge to a semantic query"""
        if query_id not in self.queries:
            raise ValueError(f"Query {query_id} not found")
        
        # Validate edge
        source_exists = any(node.id == edge.source_node_id for node in self.queries[query_id].nodes)
        target_exists = any(node.id == edge.target_node_id for node in self.queries[query_id].nodes)
        
        if not source_exists or not target_exists:
            raise ValueError("Source or target node not found")
        
        # Ensure edge has timestamps
        now = datetime.now()
        if not edge.created_at:
            edge.created_at = now
        edge.updated_at = now
        
        self.queries[query_id].edges.append(edge)
        self.queries[query_id].updated_at = now
        
        return edge
    
    def remove_node(self, query_id: str, node_id: str) -> bool:
        """Remove a node and its connected edges from a query"""
        if query_id not in self.queries:
            raise ValueError(f"Query {query_id} not found")
        
        query = self.queries[query_id]
        
        # Remove the node
        query.nodes = [n for n in query.nodes if n.id != node_id]
        
        # Remove connected edges
        query.edges = [e for e in query.edges 
                      if e.source_node_id != node_id and e.target_node_id != node_id]
        
        query.updated_at = datetime.now()
        return True
    
    def remove_edge(self, query_id: str, edge_id: str) -> bool:
        """Remove an edge from a query"""
        if query_id not in self.queries:
            raise ValueError(f"Query {query_id} not found")
        
        query = self.queries[query_id]
        query.edges = [e for e in query.edges if e.id != edge_id]
        query.updated_at = datetime.now()
        return True
    
    async def translate_to_natural_language(self, query_id: str) -> QueryTranslation:
        """Use AI to translate visual query to natural language"""
        if query_id not in self.queries:
            raise ValueError(f"Query {query_id} not found")
        
        query = self.queries[query_id]
        
        # Create a description of the visual query for AI analysis
        query_description = self._create_query_description(query)
        
        # Use LLM to generate natural language translation
        prompt = f"""
        Translate this visual database query into natural language:
        
        {query_description}
        
        Provide a clear, business-friendly description of what this query does.
        """
        
        response = await self.llm_analyzer.analyze_text(prompt)
        
        translation = QueryTranslation(
            query_id=query_id,
            natural_language=response.get('analysis', 'Unable to translate query'),
            confidence_score=response.get('confidence', 0.7),
            suggestions=response.get('suggestions', []),
            generated_at=datetime.now()
        )
        
        return translation
    
    async def generate_insights(self, query_id: str) -> List[QueryInsight]:
        """Generate AI insights from the semantic query"""
        if query_id not in self.queries:
            raise ValueError(f"Query {query_id} not found")
        
        query = self.queries[query_id]
        query_description = self._create_query_description(query)
        
        prompt = f"""
        Analyze this database query and provide business insights:
        
        {query_description}
        
        Consider:
        1. What business questions this query answers
        2. Potential optimizations
        3. Business value and implications
        4. Related queries that might be useful
        """
        
        response = await self.llm_analyzer.analyze_text(prompt)
        
        insights = []
        if 'analysis' in response:
            insight = QueryInsight(
                query_id=query_id,
                insight_type="business_analysis",
                description=response['analysis'],
                confidence_score=response.get('confidence', 0.7),
                recommendations=response.get('suggestions', []),
                generated_at=datetime.now()
            )
            insights.append(insight)
        
        return insights
    
    def export_query(self, query_id: str, export_format: ExportFormat) -> QueryExport:
        """Export query in various formats"""
        if query_id not in self.queries:
            raise ValueError(f"Query {query_id} not found")
        
        query = self.queries[query_id]
        
        if export_format == ExportFormat.SQL:
            content = self._generate_sql(query)
        elif export_format == ExportFormat.PYTHON:
            content = self._generate_python(query)
        elif export_format == ExportFormat.R:
            content = self._generate_r(query)
        elif export_format == ExportFormat.JSON:
            content = json.dumps(self._query_to_dict(query), indent=2)
        else:
            content = self._generate_natural_language(query)
        
        export = QueryExport(
            query_id=query_id,
            export_format=export_format,
            content=content,
            metadata={
                'export_format': export_format.value,
                'query_name': query.name,
                'node_count': len(query.nodes),
                'edge_count': len(query.edges)
            },
            exported_at=datetime.now()
        )
        
        return export
    
    def _create_query_description(self, query: SemanticQuery) -> str:
        """Create a text description of the visual query for AI analysis"""
        description = f"Query: {query.name}\nDescription: {query.description}\n\n"
        
        # Describe nodes
        description += "Nodes:\n"
        for node in query.nodes:
            description += f"- {node.node_type.value}: {node.name} (ID: {node.id})\n"
            if node.properties:
                description += f"  Properties: {node.properties}\n"
        
        # Describe edges
        description += "\nConnections:\n"
        for edge in query.edges:
            source_node = next((n for n in query.nodes if n.id == edge.source_node_id), None)
            target_node = next((n for n in query.nodes if n.id == edge.target_node_id), None)
            
            if source_node and target_node:
                description += f"- {source_node.name} --[{edge.edge_type.value}]--> {target_node.name}\n"
                if edge.conditions:
                    description += f"  Conditions: {edge.conditions}\n"
        
        return description
    
    def _generate_sql(self, query: SemanticQuery) -> str:
        """Generate SQL from visual query"""
        # This is a simplified SQL generation - in practice, you'd want more sophisticated logic
        sql_parts = ["SELECT"]
        
        # Find SELECT nodes
        select_nodes = []
        for edge in query.edges:
            if edge.edge_type == QueryEdgeType.SELECT:
                target_node = next((n for n in query.nodes if n.id == edge.target_node_id), None)
                if target_node:
                    select_nodes.append(target_node.name)
        
        if select_nodes:
            sql_parts.append(", ".join(select_nodes))
        else:
            sql_parts.append("*")
        
        # Find FROM nodes (tables)
        table_nodes = [n for n in query.nodes if n.node_type == QueryNodeType.TABLE]
        if table_nodes:
            sql_parts.append("FROM")
            sql_parts.append(", ".join(n.name for n in table_nodes))
        
        # Find WHERE conditions
        where_edges = [e for e in query.edges if e.edge_type == QueryEdgeType.WHERE]
        if where_edges:
            sql_parts.append("WHERE")
            where_conditions = []
            for edge in where_edges:
                if edge.conditions:
                    where_conditions.append(str(edge.conditions))
            if where_conditions:
                sql_parts.append(" AND ".join(where_conditions))
        
        return " ".join(sql_parts) + ";"
    
    def _generate_python(self, query: SemanticQuery) -> str:
        """Generate Python code from visual query"""
        code_lines = [
            "import pandas as pd",
            "",
            "# Generated from visual query builder",
            f"# Query: {query.name}",
            ""
        ]
        
        # Find table nodes for data loading
        table_nodes = [n for n in query.nodes if n.node_type == QueryNodeType.TABLE]
        for table in table_nodes:
            code_lines.append(f"# Load {table.name} data")
            code_lines.append(f"{table.name.lower()}_df = pd.read_csv('{table.name.lower()}.csv')")
            code_lines.append("")
        
        # Generate query logic based on edges
        select_edges = [e for e in query.edges if e.edge_type == QueryEdgeType.SELECT]
        if select_edges and table_nodes:
            code_lines.append("# Select columns")
            select_columns = []
            for edge in select_edges:
                target_node = next((n for n in query.nodes if n.id == edge.target_node_id), None)
                if target_node:
                    select_columns.append(target_node.name)
            
            if select_columns:
                main_table = table_nodes[0].name.lower()
                code_lines.append(f"result = {main_table}_df[{select_columns}]")
        
        code_lines.append("")
        code_lines.append("print(result.head())")
        
        return "\n".join(code_lines)
    
    def _generate_r(self, query: SemanticQuery) -> str:
        """Generate R code from visual query"""
        code_lines = [
            "# Generated from visual query builder",
            f"# Query: {query.name}",
            ""
        ]
        
        # Find table nodes for data loading
        table_nodes = [n for n in query.nodes if n.node_type == QueryNodeType.TABLE]
        for table in table_nodes:
            code_lines.append(f"# Load {table.name} data")
            code_lines.append(f"{table.name.lower()}_df <- read.csv('{table.name.lower()}.csv')")
            code_lines.append("")
        
        # Generate query logic
        select_edges = [e for e in query.edges if e.edge_type == QueryEdgeType.SELECT]
        if select_edges and table_nodes:
            code_lines.append("# Select columns")
            select_columns = []
            for edge in select_edges:
                target_node = next((n for n in query.nodes if n.id == edge.target_node_id), None)
                if target_node:
                    select_columns.append(f"'{target_node.name}'")
            
            if select_columns:
                main_table = table_nodes[0].name.lower()
                code_lines.append(f"result <- {main_table}_df[, c({', '.join(select_columns)})]")
        
        code_lines.append("")
        code_lines.append("head(result)")
        
        return "\n".join(code_lines)
    
    def _generate_natural_language(self, query: SemanticQuery) -> str:
        """Generate natural language description"""
        return self._create_query_description(query)
    
    def _query_to_dict(self, query: SemanticQuery) -> Dict[str, Any]:
        """Convert query to dictionary for JSON export"""
        return {
            'id': query.id,
            'name': query.name,
            'description': query.description,
            'nodes': [
                {
                    'id': n.id,
                    'name': n.name,
                    'type': n.node_type.value,
                    'position': n.position,
                    'properties': n.properties
                }
                for n in query.nodes
            ],
            'edges': [
                {
                    'id': e.id,
                    'source': e.source_node_id,
                    'target': e.target_node_id,
                    'type': e.edge_type.value,
                    'properties': e.properties,
                    'conditions': e.conditions
                }
                for e in query.edges
            ],
            'metadata': query.metadata,
            'version': query.version
        }
    
    def get_query(self, query_id: str) -> Optional[SemanticQuery]:
        """Get a query by ID"""
        return self.queries.get(query_id)
    
    def list_queries(self) -> List[SemanticQuery]:
        """List all queries"""
        return list(self.queries.values())
    
    def delete_query(self, query_id: str) -> bool:
        """Delete a query"""
        if query_id in self.queries:
            del self.queries[query_id]
            return True
        return False
