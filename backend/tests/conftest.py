"""
Pytest configuration and fixtures
"""

import pytest
import asyncio
from typing import Generator
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from backend.shared.models.transaction import NormalizedTransaction, EventType, TransactionStatus, ReconciliationStatus
from backend.shared.models.settlement import PSPSettlement
from backend.shared.models.tenant import Tenant, Brand, Entity


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container():
    """PostgreSQL test container"""
    with PostgresContainer("postgres:15") as postgres:
        yield postgres


@pytest.fixture
def db_session(postgres_container):
    """Database session for tests"""
    engine = create_engine(postgres_container.get_connection_url())
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_tenant_id() -> UUID:
    """Test tenant ID"""
    return uuid4()


@pytest.fixture
def test_brand_id() -> UUID:
    """Test brand ID"""
    return uuid4()


@pytest.fixture
def test_entity_id() -> UUID:
    """Test entity ID"""
    return uuid4()


@pytest.fixture
def sample_transaction(test_tenant_id: UUID, test_brand_id: UUID, test_entity_id: UUID) -> dict:
    """Sample normalized transaction for testing"""
    return {
        'transaction_id': uuid4(),
        'tenant_id': test_tenant_id,
        'brand_id': test_brand_id,
        'entity_id': test_entity_id,
        'psp_connection_id': 'psp_stripe_test_001',
        'event_type': EventType.DEPOSIT,
        'event_timestamp': '2024-01-15T10:30:00Z',
        'transaction_date': '2024-01-15',
        'amount_value': 100000,  # $1000.00 in cents
        'amount_currency': 'USD',
        'psp_transaction_id': 'txn_test_123',
        'psp_payment_id': 'pay_test_456',
        'status': TransactionStatus.COMPLETED,
        'reconciliation_status': ReconciliationStatus.PENDING,
        'source_type': 'WEBHOOK',
        'source_idempotency_key': 'test:txn_test_123:DEPOSIT:1705315800'
    }


@pytest.fixture
def sample_settlement(test_tenant_id: UUID) -> dict:
    """Sample PSP settlement for testing"""
    return {
        'settlement_id': uuid4(),
        'tenant_id': test_tenant_id,
        'psp_connection_id': 'psp_stripe_test_001',
        'settlement_date': '2024-01-15',
        'settlement_batch_id': 'batch_20240115_001',
        'settlement_line_number': 1,
        'amount_value': 97100,  # $971.00 in cents (after $29 fee)
        'amount_currency': 'USD',
        'psp_transaction_ids': ['txn_test_123'],
        'psp_fee': 2900,  # $29.00 in cents
        'net_amount': 97100
    }


