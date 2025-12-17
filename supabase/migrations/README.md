# Supabase Migrations

This directory contains Supabase migrations for the PSP Reconciliation Platform.

## Migration Strategy

Migrations are applied using Supabase MCP tools:
- `apply_migration`: For DDL operations (CREATE, ALTER, DROP)
- `execute_sql`: For DML operations (INSERT, UPDATE, DELETE)

## Migration Files

- `001_initial_schema.sql`: Initial database schema
  - Note: Full schema is in `database/migrations/001_initial_schema.sql`
  - This file references that for Supabase migration application

## Applying Migrations

### Via MCP Tool

```python
# Apply migration
apply_migration(
    name="001_initial_schema",
    query="<SQL from database/migrations/001_initial_schema.sql>"
)
```

### Via Supabase CLI

```bash
supabase migration up
```

### Via Supabase Dashboard

1. Go to Supabase Dashboard
2. Navigate to SQL Editor
3. Paste migration SQL
4. Execute

## Migration Best Practices

1. **Always test migrations in staging first**
2. **Use transactions for data migrations**
3. **Never hardcode generated IDs**
4. **Version migrations with timestamps or sequential numbers**
5. **Document breaking changes**

## Rollback

To rollback a migration:

```sql
-- Create rollback migration
-- Apply via apply_migration with name "rollback_001_initial_schema"
```

## Branch Management

Use Supabase branch management for schema versioning:
- `create_branch`: Create feature branch for schema changes
- `merge_branch`: Merge branch after testing
- `delete_branch`: Clean up after merge


