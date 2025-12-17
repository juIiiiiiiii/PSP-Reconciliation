#!/bin/bash
# Deploy to Render

set -e

echo "Deploying to Render..."

# Check if Render CLI is installed
if ! command -v render &> /dev/null; then
    echo "Error: Render CLI not found. Install with: npm install -g @render/cli"
    exit 1
fi

# Deploy services
echo "Deploying API service..."
render deploy --service psp-reconciliation-api

echo "Deploying scheduler worker..."
render deploy --service psp-reconciliation-scheduler

echo "Deployment to Render completed successfully!"


