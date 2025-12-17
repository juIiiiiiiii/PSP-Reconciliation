#!/bin/bash
# Deploy Supabase Edge Function for webhook handling

set -e

echo "Deploying Supabase Edge Function..."

# Check if Supabase CLI is installed
if ! command -v supabase &> /dev/null; then
    echo "Error: Supabase CLI not found. Install with: npm install -g supabase"
    exit 1
fi

# Check if logged in
if ! supabase projects list &> /dev/null; then
    echo "Error: Not logged in to Supabase. Run: supabase login"
    exit 1
fi

# Deploy webhook handler edge function
echo "Deploying webhook-handler function..."
supabase functions deploy webhook-handler \
  --project-ref "${SUPABASE_PROJECT_REF}" \
  --no-verify-jwt

echo "Edge function deployed successfully!"


