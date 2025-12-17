# Local Setup Complete ✅

The PSP Reconciliation Platform is now running locally!

## Services Running

- **API**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## Quick Access

- **Health Check**: http://localhost:8000/health
- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **ReDoc Documentation**: http://localhost:8000/redoc

## Status

✅ All services are running and healthy
✅ API is responding to requests
✅ Database and Redis are connected

## Next Steps

1. **Access the API**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **View API Documentation**:
   Open http://localhost:8000/docs in your browser

3. **Run Database Migrations** (if needed):
   ```bash
   docker compose exec api python -m alembic upgrade head
   ```

4. **View Logs**:
   ```bash
   docker compose logs -f api
   ```

5. **Stop Services**:
   ```bash
   docker compose down
   # or
   make stop
   ```

## Common Commands

```bash
# Start services
make start
# or
./scripts/start_local.sh

# Stop services
make stop
# or
./scripts/stop_local.sh

# View logs
make logs
make logs-api

# Restart services
make restart

# Check status
make status
# or
docker compose ps
```

## Troubleshooting

If you encounter issues:

1. **Check service status**:
   ```bash
   docker compose ps
   ```

2. **View logs**:
   ```bash
   docker compose logs api
   ```

3. **Restart services**:
   ```bash
   docker compose restart
   ```

4. **Rebuild containers**:
   ```bash
   docker compose build --no-cache
   docker compose up -d
   ```

## Development

The API service has hot-reload enabled, so code changes will automatically restart the service.

To make changes:
1. Edit files in `backend/`
2. Changes are automatically detected and reloaded
3. Check logs to see if changes were applied

## Database Access

Connect to PostgreSQL:
```bash
docker compose exec postgres psql -U postgres -d psp_reconciliation
```

Or use any PostgreSQL client:
- Host: localhost
- Port: 5432
- Database: psp_reconciliation
- User: postgres
- Password: postgres

## Redis Access

Connect to Redis:
```bash
docker compose exec redis redis-cli
```

## Notes

- Default JWT secret is set to `dev-secret-key-change-in-production` (change in production!)
- Database migrations are automatically applied on first startup
- All services are configured for local development

Enjoy developing! 🚀


