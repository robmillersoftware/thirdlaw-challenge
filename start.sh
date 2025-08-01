#!/bin/bash

# PDF Sensitive Data Scanner - Startup Script

echo "🔍 Starting PDF Sensitive Data Scanner..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Start ClickHouse
echo "📊 Starting ClickHouse database..."
docker-compose up -d

# Wait for ClickHouse to be ready
echo "⏳ Waiting for ClickHouse to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8123 >/dev/null 2>&1; then
        echo "✅ ClickHouse is ready!"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo "❌ ClickHouse failed to start within 30 seconds"
        exit 1
    fi
done

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment and install dependencies
echo "📦 Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt >/dev/null 2>&1

# Start the application
echo "🚀 Starting PDF Scanner server..."
echo "🌐 Access the application at: http://localhost:8000"
echo "📚 API documentation at: http://localhost:8000/docs"
echo "🔗 ClickHouse admin at: http://localhost:8123"
echo ""
echo "Press Ctrl+C to stop the server"

cd backend
python main.py