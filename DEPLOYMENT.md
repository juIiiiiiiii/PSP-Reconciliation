# Deployment Guide

This guide covers deployment of the PSP Reconciliation Platform using MCP servers.

## Prerequisites

1. **Supabase Account**: https://supabase.com
2. **Cloudflare Account**: https://cloudflare.com
3. **Render Account**: https://render.com
4. **GitHub Account**: https://github.com
5. **n8n Instance**: Self-hosted or cloud

## Deployment Steps

### 1. Supabase Setup

1. Create Supabase project
2. Get project URL and service role key
3. Set environment variables:
   ```bash
   export SUPABASE_URL=https://your-project.supabase.co
   export SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   export DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```
4. Apply migrations:
   ```bash
   ./scripts/deploy_supabase_edge_function.sh
   ```

### 2. Cloudflare Setup

1. Create Cloudflare account
2. Get account ID and API token
3. Set environment variables:
   ```bash
   export CLOUDFLARE_ACCOUNT_ID=your-account-id
   export CLOUDFLARE_API_TOKEN=your-api-token
   export CLOUDFLARE_R2_ACCESS_KEY_ID=your-r2-access-key
   export CLOUDFLARE_R2_SECRET_ACCESS_KEY=your-r2-secret-key
   ```
4. Create R2 buckets:
   ```bash
   ./scripts/setup_cloudflare_r2.sh
   ```
5. Deploy Workers:
   ```bash
   ./scripts/deploy_cloudflare_worker.sh
   ```

### 3. Render Setup

1. Create Render account
2. Get API key
3. Set environment variable:
   ```bash
   export RENDER_API_KEY=your-api-key
   ```
4. Deploy services:
   ```bash
   ./scripts/deploy_render.sh
   ```

### 4. GitHub Actions Setup

1. Create GitHub repository
2. Set up secrets in GitHub:
   - `DATABASE_URL`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `CLOUDFLARE_ACCOUNT_ID`
   - `CLOUDFLARE_API_TOKEN`
   - `RENDER_API_KEY`
   - `DOCKER_USERNAME`
   - `DOCKER_PASSWORD`
3. Push code to trigger CI/CD

### 5. n8n Setup

1. Deploy n8n instance
2. Import workflows from `n8n/workflows/`
3. Configure API credentials
4. Activate workflows

## Environment Variables

### Required

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `JWT_SECRET`: JWT signing secret
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key

### Optional

- `CLOUDFLARE_ACCOUNT_ID`: Cloudflare account ID
- `CLOUDFLARE_R2_ACCESS_KEY_ID`: R2 access key
- `CLOUDFLARE_R2_SECRET_ACCESS_KEY`: R2 secret key
- `RENDER_API_KEY`: Render API key
- `N8N_API_URL`: n8n API URL
- `N8N_API_KEY`: n8n API key

## Verification

After deployment, verify:

1. **Health Check**: `curl https://api.psp-reconciliation.com/health`
2. **Database**: Connect to Supabase database
3. **R2 Buckets**: List buckets in Cloudflare dashboard
4. **Workers**: Test webhook validation
5. **Render Services**: Check service status
6. **CI/CD**: Verify GitHub Actions runs
7. **n8n Workflows**: Test workflow execution

## Troubleshooting

### Supabase Issues
- Check connection string format
- Verify service role key permissions
- Check database logs in Supabase dashboard

### Cloudflare Issues
- Verify R2 access keys
- Check Worker logs
- Verify KV namespace bindings

### Render Issues
- Check service logs
- Verify environment variables
- Check build logs

### GitHub Actions Issues
- Check workflow logs
- Verify secrets are set
- Check branch protection rules

## Rollback

To rollback deployment:

1. **Supabase**: Use migration rollback
2. **Cloudflare**: Deploy previous Worker version
3. **Render**: Deploy previous service version
4. **GitHub**: Revert commit and redeploy

## Monitoring

Monitor deployment:

1. **Supabase**: Dashboard metrics
2. **Cloudflare**: Analytics dashboard
3. **Render**: Service metrics
4. **GitHub**: Actions status
5. **n8n**: Execution logs


