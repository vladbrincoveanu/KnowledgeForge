# KnowledgeForge Ontology Extraction API Makefile

.PHONY: help install test run build up down logs clean lint format

# Default target
help:
	@echo "KnowledgeForge Ontology Extraction API"
	@echo "======================================"
	@echo ""
	@echo "Available commands:"
	@echo "  install     - Install Python dependencies"
	@echo "  test        - Run API tests"
	@echo "  run         - Run API locally"
	@echo "  build       - Build Docker image"
	@echo "  up          - Start all services with Docker Compose"
	@echo "  down        - Stop all services"
	@echo "  logs        - View service logs"
	@echo "  clean       - Clean up temporary files"
	@echo "  lint        - Run code linting"
	@echo "  format      - Format code with Black"
	@echo "  setup       - Initial setup and configuration"
	@echo "  health      - Check service health"
	@echo "  docs        - Generate API documentation"

# Install dependencies
install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "✅ Dependencies installed"

# Run tests
test:
	@echo "Running API tests..."
	python test_api.py
	@echo "✅ Tests completed"

# Run API locally
run:
	@echo "Starting KnowledgeForge API locally..."
	python main.py

# Build Docker image
build:
	@echo "Building Docker image..."
	docker build -t knowledgeforge-api:latest .
	@echo "✅ Docker image built"

# Start all services
up:
	@echo "Starting all services with Docker Compose..."
	docker-compose up -d
	@echo "✅ Services started"
	@echo "🌐 API: http://localhost:8000"
	@echo "📊 Neo4j: http://localhost:7474"
	@echo "📚 API Docs: http://localhost:8000/docs"

# Stop all services
down:
	@echo "Stopping all services..."
	docker-compose down
	@echo "✅ Services stopped"

# View logs
logs:
	@echo "Viewing service logs..."
	docker-compose logs -f

# Clean up
clean:
	@echo "Cleaning up temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete
	find . -type f -name "*.db" -delete
	find . -type f -name "test_*.csv" -delete
	@echo "✅ Cleanup completed"

# Run linting
lint:
	@echo "Running code linting..."
	flake8 .
	pylint ontology_extractor/ main.py
	@echo "✅ Linting completed"

# Format code
format:
	@echo "Formatting code with Black..."
	black .
	@echo "✅ Code formatting completed"

# Initial setup
setup:
	@echo "Setting up KnowledgeForge API..."
	@echo "Creating necessary directories..."
	mkdir -p data logs uploads cache
	@echo "Setting up configuration..."
	@if [ ! -f config.yaml ]; then \
		echo "Creating default config.yaml..."; \
		cp config.yaml.example config.yaml 2>/dev/null || echo "Please create config.yaml manually"; \
	fi
	@echo "Installing dependencies..."
	$(MAKE) install
	@echo "✅ Setup completed"
	@echo ""
	@echo "Next steps:"
	@echo "1. Configure config.yaml with your settings"
	@echo "2. Start services: make up"
	@echo "3. Run tests: make test"

# Check service health
health:
	@echo "Checking service health..."
	@echo "🔍 API Health:"
	@curl -s http://localhost:8000/health | jq . 2>/dev/null || echo "API not responding"
	@echo ""
	@echo "🔍 API Readiness:"
	@curl -s http://localhost:8000/ready | jq . 2>/dev/null || echo "API not ready"
	@echo ""
	@echo "🔍 Docker Services:"
	@docker-compose ps

# Generate API documentation
docs:
	@echo "Generating API documentation..."
	@if [ -f main.py ]; then \
		echo "API documentation available at:"; \
		echo "  - Swagger UI: http://localhost:8000/docs"; \
		echo "  - ReDoc: http://localhost:8000/redoc"; \
		echo "  - OpenAPI JSON: http://localhost:8000/openapi.json"; \
	else \
		echo "API not running. Start with: make up"; \
	fi

# Development mode with hot reload
dev:
	@echo "Starting development mode with hot reload..."
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode
prod:
	@echo "Starting production mode..."
	uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Database operations
db-init:
	@echo "Initializing database..."
	@echo "This will create necessary Neo4j constraints and indexes"
	@echo "Make sure Neo4j is running first: make up"
	@echo "Then run the integration example: python ontology_extractor/integration_example.py"

# Backup data
backup:
	@echo "Creating backup..."
	@mkdir -p backups
	@tar -czf backups/knowledgeforge-$(shell date +%Y%m%d-%H%M%S).tar.gz \
		data/ logs/ uploads/ config.yaml
	@echo "✅ Backup created in backups/ directory"

# Restore from backup
restore:
	@echo "Available backups:"
	@ls -la backups/ 2>/dev/null || echo "No backups found"
	@echo ""
	@echo "To restore, manually extract the backup file to the project root"

# Performance testing
perf-test:
	@echo "Running performance tests..."
	@echo "This will test the API with various load scenarios"
	@echo "Make sure the API is running first: make up"
	@echo "Then run: python test_api.py"

# Security scan
security-scan:
	@echo "Running security scan..."
	@echo "Checking for known vulnerabilities..."
	@echo "This requires additional security tools to be installed"
	@echo "Consider using: bandit, safety, or similar tools"

# Update dependencies
update-deps:
	@echo "Updating dependencies..."
	pip install --upgrade -r requirements.txt
	@echo "✅ Dependencies updated"

# Show service status
status:
	@echo "Service Status:"
	@echo "==============="
	@docker-compose ps
	@echo ""
	@echo "Resource Usage:"
	@echo "==============="
	@docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

# Interactive shell
shell:
	@echo "Starting interactive shell..."
	@docker-compose exec api /bin/bash

# Monitor logs in real-time
monitor:
	@echo "Monitoring all services in real-time..."
	@docker-compose logs -f --tail=100

# Scale services
scale:
	@echo "Scaling API service..."
	@echo "Current scale:"
	@docker-compose ps api
	@echo ""
	@echo "To scale up: docker-compose up -d --scale api=3"
	@echo "To scale down: docker-compose up -d --scale api=1"

# Show help for specific command
help-%:
	@echo "Help for command: $*"
	@echo "=================="
	@$(MAKE) -n $* | head -20
