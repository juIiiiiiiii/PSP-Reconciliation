# Local Development Guide

This guide explains how to run the PSP Reconciliation Platform locally using Docker.

## Prerequisites

- Docker and Docker Compose installed
- At least 4GB of free RAM
- Ports 8000, 5432, 6379 available (or modify in docker-compose.yml)

## Quick Start

1. **Clone and navigate to the project**:
   ```bash
   cd "PSP Reconciliation"
   ```

2. **Start the platform**:
   ```bash
   make start
   # or
   ./scripts/start_local.sh
   ```

3. **Access the API**:
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## Services

The platform runs the following services:

- **API** (port 8000): FastAPI application
- **PostgreSQL** (port 5432): Database
- **Redis** (port 6379): Cache and idempotency storage
- **LocalStack** (port 4566, optional): AWS services simulation

## Configuration

### Environment Variables

Copy `.env.local` to `.env` and update as needed:

```bash
cp .env.local .env
```

Key variables:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `JWT_SECRET`: JWT signing secret (change in production)
- `AWS_ENDPOINT_URL`: LocalStack endpoint (if using LocalStack)

### AWS Services (Optional)

For local development, you can use LocalStack to simulate AWS services:

```bash
make setup-localstack
# or
./scripts/setup_localstack.sh
```

This creates:
- S3 buckets for raw events, settlements, and archive
- Kinesis stream for events
- DynamoDB table for idempotency

## Common Commands

### Start/Stop Services

```bash
# Start all services
make start

# Stop all services
make stop

# Restart services
make restart

# View logs
make logs

# View API logs only
make logs-api
```

### Database

```bash
# Open PostgreSQL shell
make shell-db

# Run migrations
make migrate
```

### Development

```bash
# Run tests
make test

# Open shell in API container
make shell-api

# Check service status
make status
```

### Cleanup

```bash
# Stop and remove all containers and volumes
make clean
```

## API Endpoints

Once running, you can access:

- **Health Check**: `GET /health`
- **API Documentation**: `GET /docs` (Swagger UI)
- **ReDoc Documentation**: `GET /redoc`
- **Reconciliation Stats**: `GET /api/v1/reconciliations/stats`
- **List Exceptions**: `GET /api/v1/exceptions`
- **Create Manual Match**: `POST /api/v1/matches/manual`

## Troubleshooting

### Port Already in Use

If ports are already in use, modify `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Change 8000 to 8001
```

### Database Connection Issues

1. Check if PostgreSQL is running:
   ```bash
   docker-compose ps postgres
   ```

2. Check logs:
   ```bash
   docker-compose logs postgres
   ```

3. Restart services:
   ```bash
   make restart
   ```

### API Not Starting

1. Check API logs:
   ```bash
   make logs-api
   ```

2. Check if dependencies are installed:
   ```bash
   make shell-api
   pip list
   ```

3. Rebuild containers:
   ```bash
   docker-compose build --no-cache api
   docker-compose up -d api
   ```

### Database Migrations

If you need to run migrations manually:

```bash
# Connect to API container
docker-compose exec api /bin/bash

# Run migrations
alembic upgrade head
```

## Development Workflow

1. **Start services**: `make start`
2. **Make code changes**: Edit files in `backend/`
3. **Changes auto-reload**: API service has `--reload` flag
4. **Run tests**: `make test`
5. **Check logs**: `make logs-api`
6. **Stop services**: `make stop`

## LocalStack Setup

LocalStack provides local AWS services for development:

1. Start LocalStack:
   ```bash
   docker-compose --profile aws-services up -d localstack
   ```

2. Setup resources:
   ```bash
   make setup-localstack
   ```

3. Use LocalStack endpoint:
   ```bash
   export AWS_ENDPOINT_URL=http://localhost:4566
   ```

## Next Steps

- Set up Supabase for database management (optional)
- Configure Cloudflare R2 for storage (optional)
- Set up n8n workflows (optional)
- Review API documentation at http://localhost:8000/docs

## Production Deployment

For production deployment, see `DEPLOYMENT.md`.


