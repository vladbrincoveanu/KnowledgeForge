# KnowledgeForge - Unified Project Management
# This Makefile provides commands to manage the entire KnowledgeForge stack

.PHONY: help up down clean logs status install test tests e2e api ui dev prod build build-docker fix

# Default target
help:
	@echo "KnowledgeForge - Available Commands:"
	@echo ""
	@echo "  make up         - Start all services (UI, API, and infrastructure)"
	@echo "  make down       - Stop all services"
	@echo "  make dev        - Start development environment"
	@echo "  make prod       - Start production environment"
	@echo "  make clean      - Stop and clean all containers and volumes"
	@echo "  make logs       - View logs from all services"
	@echo "  make status     - Show status of all services"
	@echo "  make install    - Install dependencies for API and UI"
	@echo "  make test       - Run API tests only"
	@echo "  make e2e        - Run end-to-end tests"
	@echo "  make tests      - Run all tests (API, UI, E2E)"
	@echo "  make build      - Build all projects with quality checks (format, lint, compile)"
	@echo "  make build-docker - Build Docker images only"
	@echo "  make fix        - Fix code formatting and linting issues (API: black, UI: fix-all)"
	@echo ""
	@echo "Individual Services:"
	@echo "  make api-only   - Start API only (local development)"
	@echo "  make ui-only    - Start UI only (local development)"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make infra      - Start infrastructure services only"
	@echo "  make mongo      - Open MongoDB Express (http://localhost:8081)"
	@echo "  make redis      - Open Redis Commander (http://localhost:8082)"
	@echo "  make neo4j      - Open Neo4j Browser (http://localhost:7474)"
	@echo "  make portainer  - Open Portainer (http://localhost:9002)"
	@echo ""

# Start all services (UI, API, and infrastructure)
up:
	@echo "🚀 Starting KnowledgeForge stack..."
	docker-compose up -d
	@echo "✅ All services started!"
	@echo ""
	@echo "🌐 Access points:"
	@echo "  - UI (Frontend):      http://localhost:3000"
	@echo "  - API (Backend):      http://localhost:8000"
	@echo "  - API Documentation:  http://localhost:8000/docs"
	@echo "  - Neo4j Browser:      http://localhost:7474 (neo4j/password)"
	@echo "  - MongoDB Express:    http://localhost:8081 (admin/knowlly123)"
	@echo "  - Redis Commander:    http://localhost:8082"
	@echo "  - MinIO Console:      http://localhost:9001 (minioadmin/knowlly123)"
	@echo "  - Portainer:          http://localhost:9002"
	@echo ""
	@echo "📋 To view logs: make logs"
	@echo "📊 To check status: make status"

# Alias for up command
dev: up

# Production environment (same as up for now, can be customized later)
prod:
	@echo "🏭 Starting KnowledgeForge in production mode..."
	docker-compose up -d
	@echo "✅ Production environment started!"

# Stop all services
down:
	@echo "🛑 Stopping KnowledgeForge stack..."
	docker-compose down
	@echo "✅ All services stopped!"

# Clean up everything (containers, volumes, images)
clean:
	@echo "🧹 Cleaning up KnowledgeForge stack..."
	docker-compose down -v --remove-orphans
	docker system prune -f
	@echo "✅ Cleanup complete!"

# View logs from all services
logs:
	@echo "📋 Viewing logs from all services..."
	docker-compose logs -f

# Show status of all services
status:
	@echo "📊 KnowledgeForge Services Status:"
	@echo ""
	docker-compose ps

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	@echo "Installing API dependencies..."
	cd sources && python3 -m venv venv || echo "Virtual environment already exists"
	cd sources && source venv/bin/activate && python3 -m pip install -r api/requirements.txt
	@echo "Installing UI dependencies..."
	cd sources/ui && npm install
	@echo "✅ Installation complete!"

# Build all projects with formatting, linting, and compilation
build:
	@echo "🔨 Building all projects with quality checks..."
	@echo ""
	@echo "📋 Building Backend API..."
	@echo "  - Formatting code with Black..."
	cd sources && source venv/bin/activate && cd api && python -m black . --check --diff || (echo "❌ Code formatting issues found. Run 'cd sources && source venv/bin/activate && cd api && python -m black .' to fix" && exit 1)
	@echo "  - Running Ruff linter..."
	cd sources && source venv/bin/activate && cd api && python -m ruff check . --exit-zero || (echo "⚠️ Some linting issues found, but continuing build")
	@echo "  - Type checking with MyPy..."
	cd sources && source venv/bin/activate && cd api && python -m mypy . --ignore-missing-imports || (echo "❌ Type checking failed" && exit 1)
	@echo "  ✅ Backend API checks passed!"
	@echo ""
	@echo "📋 Building Frontend UI..."
	@echo "  - Running fix-all script..."
	cd sources/ui && npm run fix-all
	@echo "  - Type checking..."
	cd sources/ui && npm run type-check || (echo "❌ TypeScript compilation failed" && exit 1)
	@echo "  - Linting..."
	cd sources/ui && npm run lint -- --max-warnings 0 || (echo "❌ ESLint failed or has warnings" && exit 1)
	@echo "  - Format checking..."
	cd sources/ui && npm run format:check || (echo "❌ Prettier format check failed" && exit 1)
	@echo "  - Building production bundle..."
	cd sources/ui && npm run build || (echo "❌ Production build failed" && exit 1)
	@echo "  ✅ Frontend UI build completed!"
	@echo ""
	@echo "✅ All projects built successfully with quality checks!"

# Build Docker images only (original build functionality)
build-docker:
	@echo "🔨 Building Docker images..."
	docker-compose build
	@echo "✅ Docker build complete!"

# Run API tests only
test:
	@echo "🧪 Running API tests..."
	cd sources && source venv/bin/activate && cd api && python3 -m pytest tests/ -v
	@echo "✅ API tests completed!"

# Run end-to-end tests
e2e:
	@echo "🧪 Running end-to-end tests..."
	cd sources/e2e && source ../venv/bin/activate && ./run_tests.sh --verbose
	@echo "✅ E2E tests completed!"

# Run all tests (API, UI, E2E)
tests:
	@echo "🧪 Running all tests..."
	@echo ""
	@echo "📋 Running API tests..."
	cd sources && source venv/bin/activate && cd api && python3 -m pytest tests/ -v
	@echo ""
	@echo "📋 Running UI tests..."
	cd sources/ui && npm run test
	@echo ""
	@echo "📋 Running E2E tests..."
	cd sources/e2e && source ../venv/bin/activate && ./run_tests.sh --verbose
	@echo ""
	@echo "✅ All tests completed!"

# Start API only (local development)
api-only:
	@echo "🔧 Starting API in local development mode..."
	cd sources && source venv/bin/activate && cd api && python3 app.py

# Start UI only (local development)
ui-only:
	@echo "🎨 Starting UI in local development mode..."
	cd sources/ui && npm run start

# Start infrastructure services only
infra:
	@echo "🏗️ Starting infrastructure services..."
	docker-compose up -d neo4j mongodb redis minio mongo-express redis-commander portainer
	@echo "✅ Infrastructure services started!"

# Quick access to web interfaces
mongo:
	@echo "🍃 Opening MongoDB Express..."
	@echo "URL: http://localhost:8081"
	@echo "Username: admin"
	@echo "Password: knowlly123"

redis:
	@echo "🔴 Opening Redis Commander..."
	@echo "URL: http://localhost:8082"

neo4j:
	@echo "🔗 Opening Neo4j Browser..."
	@echo "URL: http://localhost:7474"
	@echo "Username: neo4j"
	@echo "Password: password"

portainer:
	@echo "🐳 Opening Portainer..."
	@echo "URL: http://localhost:9002"

# Development helpers
restart:
	@echo "🔄 Restarting all services..."
	make down
	make up

restart-api:
	@echo "🔄 Restarting API service..."
	docker-compose restart api

restart-ui:
	@echo "🔄 Restarting UI service..."
	docker-compose restart ui

# Health check
health:
	@echo "🏥 Checking service health..."
	@echo "API Health:"
	@curl -f http://localhost:8000/health || echo "API not responding"
	@echo ""
	@echo "UI Health:"
	@curl -f http://localhost:3000 || echo "UI not responding"

# Show resource usage
resources:
	@echo "💾 Docker resource usage:"
	docker stats --no-stream

# Fix code formatting and linting issues
fix:
	@echo "🔧 Fixing code formatting and linting issues..."
	@echo ""
	@echo "📋 Fixing API code formatting..."
	cd sources && source venv/bin/activate && cd api && python -m black . --exclude "(tests/test_pipeline.py)" || echo "⚠️ Some files could not be formatted due to syntax errors"
	@echo "  ✅ API code formatting attempted!"
	@echo ""
	@echo "📋 Fixing UI code formatting and linting..."
	cd sources/ui && npm run fix-all
	@echo "  ✅ UI code formatted and linted!"
	@echo ""
	@echo "✅ Code formatting and linting completed!"
