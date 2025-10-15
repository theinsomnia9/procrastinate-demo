#!/bin/bash
# Quick start script for the Procrastinate Demo application

set -e

echo "🚀 Starting Procrastinate Demo Application"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
fi

# Start Docker services
echo "🐳 Starting PostgreSQL and pgAdmin..."
docker-compose up -d

echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 10

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Initialize database
echo "🗄️  Initializing database..."
python scripts/init_db.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 Next steps:"
echo "  1. Start the application:"
echo "     uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  2. Open in your browser:"
echo "     - API: http://localhost:8000"
echo "     - Docs: http://localhost:8000/docs"
echo "     - pgAdmin: http://localhost:5050 (admin@admin.com / admin)"
echo ""
echo "  3. Test the API:"
echo "     curl -X POST http://localhost:8000/tasks/fetch-joke"
echo ""
echo "📚 See README.md for more information"
echo ""
