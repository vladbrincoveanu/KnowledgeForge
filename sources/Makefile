# Knowlly Data Processing API - Docker Management

.PHONY: help install dev prod clean logs test

# Default target
help:
	@echo "KnowledgeForge - Available Commands:"
	@echo ""
	@echo "  make install    - Install dependencies for API and UI"
	@echo "  make dev        - Start development environment"
	@echo "  make prod       - Start production environment"
	@echo "  make clean      - Stop and clean all containers"
	@echo "  make logs       - View logs from all services"
	@echo "  make test       - Run tests"
	@echo "  make api        - Start API only (local development)"
	@echo "  make ui         - Start UI only (local development)"
	@echo ""

# Install dependencies
install:
	@echo "Installing API dependencies..."
	pip install -r requirements.txt
	@echo "Installing UI dependencies..."
	cd UI && npm install
	@echo "Installation complete!"

# Development environment
dev:
	@echo "Starting development environment..."
	docker-compose -f docker-compose.yml up -d
	@echo "Development services started!"
	@echo "Access points:"
	@echo "  - UI Dev Server: http://localhost:3000"
	@echo "  - MongoDB Express: http://localhost:8081"
	@echo "  - Redis Commander: http://localhost:8082"
	@echo "  - Portainer: http://localhost:9002"

# Production environment
prod:
	@echo "Starting production environment..."
	docker-compose up -d
	@echo "Production services started!"
	@echo "Access points:"
	@echo "  - Application: http://localhost"
	@echo "  - API: http://localhost:8000"
	@echo "  - API Docs: http://localhost/docs"
	@echo "  - MongoDB Express: http://localhost:8081"

# Clean up
clean:
	@echo "Stopping and cleaning containers..."
	docker-compose down -v
	docker-compose -f docker-compose.yml down -v
	@echo "Cleanup complete!"

# View logs
logs:
	@echo "Viewing logs from all services..."
	docker-compose logs -f

# Run tests
test:
	@echo "Running tests..."
	pytest Tests/ -v

# Start API only (local development)
api:
	@echo "Starting API in development mode..."
	python main.py

# Start UI only (local development)
ui:
	@echo "Starting UI in development mode..."
	cd UI && npm start

# Build UI for production
build-ui:
	@echo "Building UI for production..."
	cd UI && npm run build

# Quick start (production)
start:
	@echo "Quick start - Production mode..."
	make prod
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo "Application should be available at http://localhost"

# Quick start (development)
start-dev:
	@echo "Quick start - Development mode..."
	make dev
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo "UI should be available at http://localhost:3000" 