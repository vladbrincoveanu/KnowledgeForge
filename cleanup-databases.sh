#!/bin/bash

# KnowledgeForge Database Cleanup Script
# This script removes Docker volumes and restarts containers to clean up databases

set -e  # Exit on any error

echo "🧹 KnowledgeForge Database Cleanup Script"
echo "=========================================="

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Function to stop database containers
stop_containers() {
    echo "🛑 Stopping database containers..."
    docker stop knowledgeforge-postgres knowledgeforge-neo4j 2>/dev/null || echo "   Some containers may not be running"
    echo "✅ Database containers stopped"
}

# Function to remove database volumes
remove_volumes() {
    echo "🗑️  Removing database volumes..."
    
    # Remove Neo4j volumes
    echo "   Removing Neo4j volumes..."
    docker volume rm knowledgeforge-neo4j_data 2>/dev/null || echo "     neo4j_data volume not found (already removed)"
    docker volume rm knowledgeforge-neo4j_logs 2>/dev/null || echo "     neo4j_logs volume not found (already removed)"
    docker volume rm knowledgeforge-neo4j_import 2>/dev/null || echo "     neo4j_import volume not found (already removed)"
    docker volume rm knowledgeforge-neo4j_plugins 2>/dev/null || echo "     neo4j_plugins volume not found (already removed)"
    
    # Remove PostgreSQL volume
    echo "   Removing PostgreSQL volume..."
    docker volume rm knowledgeforge-postgres_data 2>/dev/null || echo "     postgres_data volume not found (already removed)"
    
    echo "✅ Database volumes removed"
}

# Function to clean up orphaned volumes (only unused volumes, not images)
cleanup_orphaned_volumes() {
    echo "🧽 Cleaning up orphaned volumes (not images)..."
    docker volume prune -f
    echo "✅ Orphaned volumes cleaned up"
}

# Function to restart database containers
restart_containers() {
    echo "🚀 Starting database containers..."
    docker-compose up -d postgres neo4j
    echo "✅ Database containers started"
}

# Function to wait for services to be healthy
wait_for_services() {
    echo "⏳ Waiting for services to be healthy..."
    
    # Wait for PostgreSQL
    echo "   Waiting for PostgreSQL..."
    timeout 60 bash -c 'until docker exec knowledgeforge-postgres pg_isready -U knowledgeforge -d knowledgeforge; do sleep 2; done' || {
        echo "❌ PostgreSQL failed to start within 60 seconds"
        exit 1
    }
    
    # Wait for Neo4j
    echo "   Waiting for Neo4j..."
    timeout 120 bash -c 'until curl -f http://localhost:7474/browser/ > /dev/null 2>&1; do sleep 5; done' || {
        echo "❌ Neo4j failed to start within 120 seconds"
        exit 1
    }
    
    
    echo "✅ Database services are healthy"
}

# Function to show status
show_status() {
    echo ""
    echo "📊 Database Service Status:"
    echo "==========================="
    echo "PostgreSQL: http://localhost:5432"
    echo "Neo4j Browser: http://localhost:7474"
    echo ""
    echo "🔐 Database Credentials:"
    echo "PostgreSQL: knowledgeforge / knowledgeforge123"
    echo "Neo4j: neo4j / password"
    echo ""
}

# Main execution
main() {
    check_docker
    stop_containers
    remove_volumes
    cleanup_orphaned_volumes
    restart_containers
    wait_for_services
    show_status
    
    echo "🎉 Database cleanup completed successfully!"
    echo "PostgreSQL and Neo4j databases have been reset and are running."
}

# Run main function
main "$@"
