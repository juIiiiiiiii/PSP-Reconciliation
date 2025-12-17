#!/bin/bash
# Stop PSP Reconciliation Platform locally

set -e

# Use docker compose (newer) or docker-compose (older)
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo "🛑 Stopping PSP Reconciliation Platform..."

$COMPOSE_CMD down

echo "✅ All services stopped!"


