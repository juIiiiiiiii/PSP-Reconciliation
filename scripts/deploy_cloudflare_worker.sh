#!/bin/bash
# Deploy Cloudflare Worker for webhook validation

set -e

echo "Deploying Cloudflare Worker..."

# Check if Wrangler CLI is installed
if ! command -v wrangler &> /dev/null; then
    echo "Error: Wrangler CLI not found. Install with: npm install -g wrangler"
    exit 1
fi

# Deploy to staging
echo "Deploying to staging..."
cd cloudflare
wrangler deploy --env staging

# Deploy to production (requires confirmation)
read -p "Deploy to production? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    wrangler deploy --env production
fi

echo "Cloudflare Worker deployed successfully!"


