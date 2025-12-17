#!/bin/bash
# Start PSP Reconciliation Platform locally using Docker Compose

set -e

echo "🚀 Starting PSP Reconciliation Platform locally..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Error: docker-compose is not installed. Please install docker-compose and try again."
    exit 1
fi

# Use docker compose (newer) or docker-compose (older)
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    if [ -f .env.local ]; then
        echo "📝 Creating .env file from .env.local..."
        cp .env.local .env
        echo "✅ .env file created. Please review and update if needed."
    else
        echo "📝 Creating .env file with default values..."
        cat > .env << EOF
# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/psp_reconciliation

# Redis
REDIS_URL=redis://redis:6379

# JWT
JWT_SECRET=dev-secret-key-change-in-production

# Environment
ENVIRONMENT=development
EOF
        echo "✅ .env file created with default values."
    fi
fi

# Build and start services
echo "🔨 Building Docker images..."
$COMPOSE_CMD build

echo "🚀 Starting services..."
$COMPOSE_CMD up -d postgres redis

echo "⏳ Waiting for database to be ready..."
sleep 5

# Wait for postgres to be ready
until $COMPOSE_CMD exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    echo "⏳ Waiting for PostgreSQL..."
    sleep 2
done

echo "✅ PostgreSQL is ready!"

# Wait for redis to be ready
until $COMPOSE_CMD exec -T redis redis-cli ping > /dev/null 2>&1; do
    echo "⏳ Waiting for Redis..."
    sleep 2
done

echo "✅ Redis is ready!"

# Start API service
echo "🚀 Starting API service..."
$COMPOSE_CMD up -d api

echo "⏳ Waiting for API to be ready..."
sleep 3

# Check if API is healthy
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API is healthy!"
else
    echo "⚠️  API might not be ready yet. Check logs with: docker-compose logs api"
fi

echo ""
echo "✅ PSP Reconciliation Platform is running!"
echo ""
echo "📍 Services:"
echo "   - API: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Health Check: http://localhost:8000/health"
echo "   - PostgreSQL: localhost:5432"
echo "   - Redis: localhost:6379"
echo ""
echo "📋 Useful commands:"
echo "   - View logs: $COMPOSE_CMD logs -f"
echo "   - Stop services: $COMPOSE_CMD down"
echo "   - Restart services: $COMPOSE_CMD restart"
echo "   - View API logs: $COMPOSE_CMD logs -f api"
echo ""

