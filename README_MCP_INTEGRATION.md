# MCP Integration Guide

This document describes the MCP (Model Context Protocol) server integrations for the PSP Reconciliation Platform.

## Overview

The platform integrates with multiple MCP servers to enhance functionality, reduce infrastructure complexity, and improve operations:

- **Supabase**: Database management, migrations, and real-time capabilities
- **Cloudflare**: R2 storage, KV, and edge computing
- **Render**: Simplified deployment and hosting
- **GitHub**: CI/CD pipeline and version control
- **n8n**: Workflow automation for operations

## Supabase Integration

### Setup

1. Create a Supabase project at https://supabase.com
2. Get your project URL and service role key
3. Set environment variables:
   ```bash
   export SUPABASE_URL=https://your-project.supabase.co
   export SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   export DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```

### Usage

The `SupabaseClient` class provides:
- Database connection pooling
- Migration management via MCP tools
- SQL execution for data quality checks

### Migrations

Apply migrations using Supabase MCP tool:
```python
# Via MCP tool call
apply_migration(
    name="add_new_column",
    query="ALTER TABLE normalized_transaction ADD COLUMN new_field VARCHAR(255);"
)
```

### Edge Functions

Webhook handlers are deployed as Supabase Edge Functions for low-latency processing.

## Cloudflare Integration

### Setup

1. Create Cloudflare account
2. Get R2 access keys
3. Set environment variables:
   ```bash
   export CLOUDFLARE_ACCOUNT_ID=your-account-id
   export CLOUDFLARE_R2_ACCESS_KEY_ID=your-access-key
   export CLOUDFLARE_R2_SECRET_ACCESS_KEY=your-secret-key
   export CLOUDFLARE_R2_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com
   ```

### Usage

The `CloudflareClient` class provides:
- R2 bucket management (S3-compatible)
- KV storage for idempotency
- Edge workers for webhook validation

### R2 Buckets

Create buckets using Cloudflare MCP tool:
```python
# Via MCP tool call
create_r2_bucket(name="psp-reconciliation-raw-events")
```

## Render Integration

### Setup

1. Create Render account
2. Get API key
3. Set environment variable:
   ```bash
   export RENDER_API_KEY=your-api-key
   ```

### Usage

The `RenderClient` class provides:
- Service deployment
- Background worker management
- Cron job configuration

## GitHub Integration

### Setup

1. Create GitHub personal access token with repo permissions
2. Set environment variable:
   ```bash
   export GITHUB_TOKEN=your-github-token
   ```

### Usage

The `GitHubClient` class provides:
- Repository management
- CI/CD workflow automation
- Issue tracking

## n8n Integration

### Setup

1. Deploy n8n instance (self-hosted or cloud)
2. Get API key
3. Set environment variables:
   ```bash
   export N8N_API_URL=https://your-n8n-instance.com/api/v1
   export N8N_API_KEY=your-api-key
   ```

### Workflows

Pre-configured workflows:
- `daily_reconciliation_report.json`: Daily report generation and distribution
- `exception_escalation.json`: Exception alert routing (P1 → PagerDuty, P2 → Slack)

Create workflows using n8n MCP tool:
```python
# Via MCP tool call
n8n_create_workflow(
    name="Custom Workflow",
    nodes=[...],
    connections={...}
)
```

## Testing

All integrations have corresponding test suites:
- Unit tests: `backend/tests/unit/`
- Integration tests: `backend/tests/integration/`
- E2E tests: `backend/tests/e2e/`

Run tests:
```bash
pytest backend/tests/unit/
pytest backend/tests/integration/
pytest backend/tests/e2e/
```

## CI/CD

GitHub Actions workflows are configured in `.github/workflows/ci.yml`:
- Lint and format checks
- Unit and integration tests
- Security scanning
- Database migration validation
- Docker image build
- Deployment to Render (staging/production)

## Production Deployment

1. Set up Supabase project
2. Create Cloudflare R2 buckets
3. Deploy to Render
4. Configure GitHub Actions secrets
5. Set up n8n workflows
6. Run smoke tests
7. Monitor and validate

## Troubleshooting

### Supabase Connection Issues
- Verify connection string format
- Check service role key permissions
- Ensure database is accessible

### Cloudflare R2 Issues
- Verify access keys
- Check bucket permissions
- Ensure endpoint URL is correct

### Render Deployment Issues
- Check API key permissions
- Verify service configuration
- Check logs in Render dashboard

### n8n Workflow Issues
- Verify API key
- Check workflow JSON syntax
- Test workflow execution manually


