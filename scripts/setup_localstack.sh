#!/bin/bash
# Setup LocalStack for local AWS services simulation

set -e

echo "🔧 Setting up LocalStack for local AWS services..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Use docker compose (newer) or docker-compose (older)
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Start LocalStack
echo "🚀 Starting LocalStack..."
$COMPOSE_CMD --profile aws-services up -d localstack

echo "⏳ Waiting for LocalStack to be ready..."
sleep 10

# Install AWS CLI if not available
if ! command -v aws &> /dev/null; then
    echo "⚠️  AWS CLI not found. Install it to create resources in LocalStack."
    echo "   Or use the LocalStack web UI at http://localhost:4566"
    exit 0
fi

# Configure AWS CLI for LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export AWS_ENDPOINT_URL=http://localhost:4566

# Create S3 buckets
echo "📦 Creating S3 buckets..."
aws --endpoint-url=http://localhost:4566 s3 mb s3://psp-reconciliation-raw-events 2>/dev/null || echo "Bucket already exists"
aws --endpoint-url=http://localhost:4566 s3 mb s3://psp-reconciliation-settlements 2>/dev/null || echo "Bucket already exists"
aws --endpoint-url=http://localhost:4566 s3 mb s3://psp-reconciliation-archive 2>/dev/null || echo "Bucket already exists"

# Create Kinesis stream
echo "📡 Creating Kinesis stream..."
aws --endpoint-url=http://localhost:4566 kinesis create-stream \
    --stream-name psp-reconciliation-events \
    --shard-count 1 2>/dev/null || echo "Stream already exists"

# Create DynamoDB table
echo "🗄️  Creating DynamoDB table..."
aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name idempotency_keys \
    --attribute-definitions AttributeName=idempotency_key,AttributeType=S \
    --key-schema AttributeName=idempotency_key,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST 2>/dev/null || echo "Table already exists"

echo ""
echo "✅ LocalStack setup complete!"
echo ""
echo "📍 LocalStack endpoint: http://localhost:4566"
echo "📍 LocalStack web UI: http://localhost:4566/_localstack/health"
echo ""
echo "📋 Created resources:"
echo "   - S3 buckets: psp-reconciliation-raw-events, psp-reconciliation-settlements, psp-reconciliation-archive"
echo "   - Kinesis stream: psp-reconciliation-events"
echo "   - DynamoDB table: idempotency_keys"
echo ""


