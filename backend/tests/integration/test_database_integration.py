"""
Integration tests with real PostgreSQL database
Uses testcontainers for isolated database testing
"""

import pytest
from uuid import uuid4
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Note: apply_migrations would need to be implemented
# For now, we'll use direct SQL execution


@pytest.mark.integration
class TestDatabaseIntegration:
    """Test database integration with testcontainers"""
    
    @pytest.fixture(scope="class")
    def postgres_container(self):
        """PostgreSQL test container"""
        with PostgresContainer("postgres:15") as postgres:
            yield postgres
    
    @pytest.fixture(scope="class")
    def db_engine(self, postgres_container):
        """Database engine"""
        engine = create_engine(postgres_container.get_connection_url())
        # Apply migrations (would use actual migration files)
        # For now, we'll skip full migration and test basic connectivity
        yield engine
        engine.dispose()
    
    @pytest.fixture
    def db_session(self, db_engine):
        """Database session"""
        SessionLocal = sessionmaker(bind=db_engine)
        session = SessionLocal()
        yield session
        session.rollback()
        session.close()
    
    def test_table_creation(self, db_session):
        """Test that tables are created"""
        result = db_session.execute(
            text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name IN ('tenant', 'normalized_transaction', 'reconciliation_match')
            """)
        ).fetchall()
        
        table_names = [row[0] for row in result]
        assert 'tenant' in table_names
        assert 'normalized_transaction' in table_names
        assert 'reconciliation_match' in table_names
    
    def test_partitioning(self, db_session):
        """Test that partitions are created"""
        result = db_session.execute(
            text("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
                AND tablename LIKE 'normalized_transaction_%'
            """)
        ).fetchall()
        
        assert len(result) > 0
    
    def test_rls_policies(self, db_session):
        """Test that RLS policies are enabled"""
        result = db_session.execute(
            text("""
                SELECT tablename, rowsecurity
                FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = 'normalized_transaction'
            """)
        ).fetchone()
        
        assert result[1] is True  # rowsecurity enabled
    
    def test_insert_with_tenant_isolation(self, db_session):
        """Test tenant isolation with RLS"""
        tenant_id_1 = uuid4()
        tenant_id_2 = uuid4()
        
        # Set current tenant context
        db_session.execute(
            text("SET app.current_tenant_id = :tenant_id"),
            {'tenant_id': str(tenant_id_1)}
        )
        
        # Insert transaction for tenant 1
        db_session.execute(
            text("""
                INSERT INTO normalized_transaction (
                    transaction_id, tenant_id, brand_id, entity_id,
                    psp_connection_id, event_type, event_timestamp, transaction_date,
                    amount_value, amount_currency, psp_transaction_id,
                    status, reconciliation_status, source_type, source_idempotency_key
                ) VALUES (
                    gen_random_uuid(), :tenant_id, gen_random_uuid(), gen_random_uuid(),
                    'psp_test', 'DEPOSIT', NOW(), CURRENT_DATE,
                    100000, 'USD', 'txn_test_1',
                    'COMPLETED', 'PENDING', 'WEBHOOK', 'test:1:123'
                )
            """),
            {'tenant_id': str(tenant_id_1)}
        )
        db_session.commit()
        
        # Try to query with tenant 2 context (should return empty)
        db_session.execute(
            text("SET app.current_tenant_id = :tenant_id"),
            {'tenant_id': str(tenant_id_2)}
        )
        
        result = db_session.execute(
            text("SELECT COUNT(*) FROM normalized_transaction")
        ).fetchone()
        
        # Should return 0 due to RLS
        assert result[0] == 0

