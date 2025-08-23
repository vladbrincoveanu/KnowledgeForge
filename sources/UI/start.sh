#!/bin/bash

# KnowledgeForge UI Startup Script
echo "🚀 Starting KnowledgeForge UI..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 16+ first."
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 16 ]; then
    echo "❌ Node.js version 16+ is required. Current version: $(node -v)"
    exit 1
fi

echo "✅ Node.js version: $(node -v)"

# Check if dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        exit 1
    fi
    echo "✅ Dependencies installed successfully"
else
    echo "✅ Dependencies already installed"
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "🔧 Creating .env file..."
    cat > .env << EOF
# KnowledgeForge UI Environment Configuration
REACT_APP_API_URL=http://localhost:8000
REACT_APP_API_KEY=test-api-key-12345
REACT_APP_ENABLE_WEBSOCKET=true
REACT_APP_DEBUG=true
EOF
    echo "✅ .env file created"
else
    echo "✅ .env file already exists"
fi

# Check if API is running
echo "🔍 Checking API availability..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API is running on http://localhost:8000"
else
    echo "⚠️  API is not running on http://localhost:8000"
    echo "   Make sure to start the KnowledgeForge API first:"
    echo "   cd ../Api && python main.py"
    echo ""
    echo "   Or use Docker Compose:"
    echo "   cd ../Api && docker-compose up -d"
    echo ""
    echo "   Continuing anyway..."
fi

# Start the development server
echo "🌐 Starting development server..."
echo "   UI will be available at: http://localhost:3000"
echo "   Press Ctrl+C to stop"
echo ""

npm start

