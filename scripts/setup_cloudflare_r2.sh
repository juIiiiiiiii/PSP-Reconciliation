#!/bin/bash
# Setup Cloudflare R2 buckets for PSP Reconciliation Platform

set -e

echo "Setting up Cloudflare R2 buckets..."

# Create R2 buckets via Cloudflare API
# Note: This requires Cloudflare API token with R2 permissions

ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID}"
API_TOKEN="${CLOUDFLARE_API_TOKEN}"

if [ -z "$ACCOUNT_ID" ] || [ -z "$API_TOKEN" ]; then
    echo "Error: CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN must be set"
    exit 1
fi

# Create raw events bucket
echo "Creating raw-events bucket..."
curl -X POST "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/r2/buckets" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{"name": "psp-reconciliation-raw-events"}'

# Create settlements bucket
echo "Creating settlements bucket..."
curl -X POST "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/r2/buckets" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{"name": "psp-reconciliation-settlements"}'

# Create archive bucket
echo "Creating archive bucket..."
curl -X POST "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/r2/buckets" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{"name": "psp-reconciliation-archive"}'

echo "R2 buckets created successfully!"


