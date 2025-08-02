# Knowlly Data Processing API - Docker Management

.PHONY: help build up down restart logs clean test dev-up dev-down

# Default target
help:
	@echo "Knowlly Data Processing API - Docker Management"
	@echo "=============================================="
	@echo ""
	@echo "Available commands:"
	@echo "  build     - Build Docker images"
	@echo "  up        - Start all services (production)"
	@echo "  down      - Stop all services"
	@echo "  restart   - Restart all services"
	@echo "  logs      - View logs for all services"
	@echo "  clean     - Stop and remove all containers, volumes, and images"
	@echo "  test      - Test Docker infrastructure"
	@echo "  dev-up    - Start development infrastructure only"
	@echo "  dev-down  - Stop development infrastructure"
	@echo "  status    - Show service status"
	@echo "  backup    - Backup data volumes"
	@echo "  restore   - Restore data volumes"

# Build Docker images
build:
	@echo "🔨 Building Docker images..."
	docker-compose build

# Start all services (production)
up:
	@echo "🚀 Starting all services..."
	docker-compose up -d
	@echo "✅ Services started. Check status with: make status"

# Stop all services
down:
	@echo "🛑 Stopping all services..."
	docker-compose down

# Restart all services
restart:
	@echo "🔄 Restarting all services..."
	docker-compose restart

# View logs for all services
logs:
	@echo "📋 Viewing logs for all services..."
	docker-compose logs -f

# Clean up everything
clean:
	@echo "🧹 Cleaning up Docker resources..."
	docker-compose down -v --rmi all
	@echo "✅ Cleanup completed"

# Test Docker infrastructure
test:
	@echo "🧪 Testing Docker infrastructure..."
	python test_docker_setup.py

# Start development infrastructure only
dev-up:
	@echo "🚀 Starting development infrastructure..."
	docker-compose -f docker-compose.dev.yml up -d
	@echo "✅ Development infrastructure started"

# Stop development infrastructure
dev-down:
	@echo "🛑 Stopping development infrastructure..."
	docker-compose -f docker-compose.dev.yml down

# Show service status
status:
	@echo "📊 Service Status:"
	docker-compose ps

# Backup data volumes
backup:
	@echo "💾 Creating backup..."
	@mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	@echo "📦 Backing up MongoDB..."
	docker exec knowlly-mongodb mongodump --out /backup
	docker cp knowlly-mongodb:/backup backups/$(shell date +%Y%m%d_%H%M%S)/mongodb
	@echo "📦 Backing up Redis..."
	docker exec knowlly-redis redis-cli BGSAVE
	@echo "✅ Backup completed in backups/$(shell date +%Y%m%d_%H%M%S)/"

# Restore data volumes (requires backup directory)
restore:
	@echo "📥 Restoring from backup..."
	@if [ -z "$(BACKUP_DIR)" ]; then \
		echo "❌ Please specify backup directory: make restore BACKUP_DIR=backups/YYYYMMDD_HHMMSS"; \
		exit 1; \
	fi
	@if [ ! -d "$(BACKUP_DIR)" ]; then \
		echo "❌ Backup directory $(BACKUP_DIR) not found"; \
		exit 1; \
	fi
	@echo "📦 Restoring MongoDB..."
	docker cp $(BACKUP_DIR)/mongodb knowlly-mongodb:/restore
	docker exec knowlly-mongodb mongorestore /restore
	@echo "✅ Restore completed"

# Quick start for development
dev: dev-up
	@echo "🎯 Development environment ready!"
	@echo "📋 Available services:"
	@echo "  - MongoDB: localhost:27017"
	@echo "  - MongoDB Express: http://localhost:8081"
	@echo "  - Redis: localhost:6379"
	@echo "  - Redis Commander: http://localhost:8082"
	@echo "  - MinIO: localhost:9000"
	@echo "  - MinIO Console: http://localhost:9001"
	@echo "  - Portainer: http://localhost:9002"
	@echo ""
	@echo "🚀 Now run: python main.py"

# Production deployment
prod: build up
	@echo "🎯 Production environment ready!"
	@echo "📋 Available services:"
	@echo "  - API: http://localhost:8000"
	@echo "  - API Docs: http://localhost:8000/docs"
	@echo "  - MongoDB Express: http://localhost:8081"
	@echo "  - MinIO Console: http://localhost:9001"

# Monitor services
monitor:
	@echo "📊 Service monitoring..."
	@echo "Press Ctrl+C to stop monitoring"
	watch -n 2 'docker-compose ps'

# Show resource usage
resources:
	@echo "💻 Resource usage:"
	docker stats --no-stream

# Update all images
update:
	@echo "🔄 Updating Docker images..."
	docker-compose pull
	docker-compose up -d --build
	@echo "✅ Images updated and services restarted" 