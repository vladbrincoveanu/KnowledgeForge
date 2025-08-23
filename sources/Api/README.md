# KnowledgeForge Ontology Extraction API

A comprehensive FastAPI-based REST API for semantic ontology extraction from CSV files with local LLM support using LM Studio, Neo4j for graph storage, and DuckDB for data processing.

## 🚀 Features

### ✅ Core API Endpoints
- **POST /extract** - Process CSV file and extract ontology
- **GET /entities** - List extracted entities with pagination
- **GET /relationships** - List discovered relationships with pagination
- **POST /feedback** - Submit validation feedback
- **GET /graph/visualize** - Return Cypher queries for visualization
- **GET /metrics** - System performance and extraction metrics
- **GET /health** - Health check for Kubernetes deployment
- **GET /ready** - Readiness check for Kubernetes deployment

### 🔌 Real-time Updates
- **WebSocket /ws** - Real-time extraction progress updates
- Background task processing with progress tracking
- Asynchronous extraction pipeline

### 🛡️ Security & Performance
- API key authentication with Bearer tokens
- Rate limiting and CORS support
- Background task processing using FastAPI BackgroundTasks
- Comprehensive error handling and validation

### 🏗️ Architecture
- **FastAPI** - Modern, fast web framework
- **Neo4j** - Graph database for ontology storage
- **LM Studio** - Local LLM service integration
- **DuckDB** - Fast analytical database for metadata
- **Docker** - Containerized deployment
- **Kubernetes** - Production deployment support

## 📋 Prerequisites

- Python 3.9+
- Docker and Docker Compose
- Neo4j database (or use provided Docker setup)
- LM Studio service (runs locally, not in Docker)

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

1. **Clone and navigate to the API directory:**
```bash
cd sources/Api
```

2. **Start all services:**
```bash
docker-compose up -d
```

3. **Access the API:**
- API: http://localhost:8000
- Neo4j Browser: http://localhost:7474
- API Documentation: http://localhost:8000/docs

### Option 2: Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set up environment variables:**
```bash
export ONTOLOGY_CONFIG_FILE=./config.yaml
export ONTOLOGY_ENVIRONMENT=development
```

3. **Start the API:**
```bash
python main.py
```

## 📖 API Usage

### Authentication

All API endpoints require authentication using Bearer tokens:

```bash
curl -H "Authorization: Bearer your-api-key-here" \
     http://localhost:8000/entities
```

### Extract Ontology from CSV

```bash
curl -X POST "http://localhost:8000/extract" \
     -H "Authorization: Bearer your-api-key-here" \
     -H "Content-Type: application/json" \
     -d '{
       "file_path": "/path/to/your/data.csv",
       "extraction_config": {
         "confidence_threshold": 0.7,
         "max_entities_per_column": 100
       }
     }'
```

Response:
```json
{
  "task_id": "uuid-here",
  "status": "pending",
  "message": "Extraction task created and queued",
  "created_at": "2024-01-15T10:30:00",
  "estimated_completion": "2024-01-15T10:35:00"
}
```

### Monitor Extraction Progress

```bash
# Check task status
curl -H "Authorization: Bearer your-api-key-here" \
     "http://localhost:8000/extract/{task_id}"

# Real-time progress via WebSocket
wscat -c ws://localhost:8000/ws
```

### Retrieve Results

```bash
# Get entities
curl -H "Authorization: Bearer your-api-key-here" \
     "http://localhost:8000/entities?task_id={task_id}&limit=50&offset=0"

# Get relationships
curl -H "Authorization: Bearer your-api-key-here" \
     "http://localhost:8000/relationships?task_id={task_id}"

# Get graph visualization
curl -H "Authorization: Bearer your-api-key-here" \
     "http://localhost:8000/graph/visualize?task_id={task_id}"
```

### Submit Feedback

```bash
curl -X POST "http://localhost:8000/feedback" \
     -H "Authorization: Bearer your-api-key-here" \
     -H "Content-Type: application/json" \
     -d '{
       "entity_id": "entity_123",
       "feedback_type": "validate_entity",
       "feedback_value": "correct",
       "confidence_delta": 0.1,
       "user_id": "user_456"
     }'
```

## 🔧 Configuration

The API uses a YAML configuration file (`config.yaml`) with the following sections:

### Neo4j Configuration
```yaml
neo4j:
  uri: "bolt://localhost:7687"
  username: "neo4j"
  password: "password"
  database: "neo4j"
```

### LM Studio Configuration
```yaml
lmstudio:
  base_url: "http://localhost:1234"
  model_name: "llama2"
  temperature: 0.7
  max_tokens: 100
  timeout: 30
  retry_attempts: 3
  use_embeddings: true
  embedding_model: "all-MiniLM-L6-v2"
  # LM Studio specific settings
  context_length: 4096
  stop_sequences: ["</s>", "<|endoftext|>"]
  top_p: 0.9
  top_k: 40
```

### Extraction Configuration
```yaml
extraction:
  confidence_threshold: 0.7
  batch_size: 1000
  max_entities_per_column: 100
```

## 🐳 Docker Deployment

### Production Docker Compose

```bash
# Start services
docker-compose -f docker-compose.yml up -d

# View logs
docker-compose logs -f api

# Scale services
docker-compose up -d --scale api=3
```

### Kubernetes Deployment

The API includes health check endpoints (`/health` and `/ready`) for Kubernetes deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: knowledgeforge-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: knowledgeforge-api
  template:
    metadata:
      labels:
        app: knowledgeforge-api
    spec:
      containers:
      - name: api
        image: knowledgeforge-api:latest
        ports:
        - containerPort: 8000
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## 📊 Monitoring and Metrics

### System Metrics

```bash
curl -H "Authorization: Bearer your-api-key-here" \
     "http://localhost:8000/metrics"
```

Response includes:
- System performance metrics
- Extraction performance metrics
- Quality assurance metrics

### Health Checks

```bash
# Health check
curl "http://localhost:8000/health"

# Readiness check
curl "http://localhost:8000/ready"
```

## 🔍 Testing

### Run Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run with coverage
pytest --cov=ontology_extractor --cov-report=html
```

### Test API Endpoints

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test with authentication
curl -H "Authorization: Bearer test-token" \
     "http://localhost:8000/entities"
```

## 🚨 Troubleshooting

### Common Issues

1. **Neo4j Connection Failed**
   - Check if Neo4j is running: `docker ps | grep neo4j`
   - Verify credentials in config.yaml
   - Check network connectivity

2. **LM Studio Service Unavailable**
   - Ensure LM Studio local server is running on port 1234
   - Check if model is downloaded in LM Studio
   - Verify LM Studio URL in configuration

3. **API Authentication Issues**
   - Ensure Bearer token is provided
   - Check token format and length
   - Verify API key validation logic

### Logs

```bash
# View API logs
docker-compose logs -f api

# View Neo4j logs
docker-compose logs -f neo4j

# View LM Studio logs
# Check the Local Server tab in LM Studio application
```

## 🔐 Security Considerations

- **API Keys**: Implement proper API key management in production
- **Rate Limiting**: Configure appropriate rate limits for your use case
- **CORS**: Restrict CORS origins in production
- **Network Security**: Use internal networks for database connections
- **SSL/TLS**: Enable HTTPS in production with proper certificates

## 📈 Performance Optimization

- **Batch Processing**: Adjust batch sizes based on available memory
- **Connection Pooling**: Configure Neo4j connection pool sizes
- **Caching**: Enable DuckDB caching for metadata operations
- **Parallel Processing**: Enable parallel processing for large datasets
- **GPU Acceleration**: Use GPU-enabled LM Studio models for faster inference

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the documentation at `/docs` endpoint
- Review the test examples for usage patterns
