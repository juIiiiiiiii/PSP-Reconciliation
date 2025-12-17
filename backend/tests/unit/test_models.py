"""
Unit tests for data models
Target: 100% coverage
"""

import pytest
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID, uuid4

from backend.shared.models.transaction import (
    NormalizedTransaction,
    EventType,
    TransactionStatus,
    ReconciliationStatus,
    Amount,
    PSPReferences,
    Source
)
from backend.shared.models.settlement import PSPSettlement
from backend.shared.models.match import (
    ReconciliationMatch,
    MatchLevel,
    MatchMethod,
    MatchStatus
)
from backend.shared.models.exception import (
    ReconciliationException,
    ExceptionType,
    ExceptionPriority,
    ExceptionStatus
)
from backend.shared.models.ledger import LedgerEntry
from backend.shared.models.chargeback import Chargeback, ChargebackStatus
from backend.shared.models.user import User, UserRole
from backend.shared.models.tenant import Tenant, Brand, Entity, PSPConnection, ConnectorType


class TestNormalizedTransaction:
    """Test NormalizedTransaction model"""
    
    def test_create_transaction(self):
        """Test creating a normalized transaction"""
        transaction = NormalizedTransaction(
            transaction_id=uuid4(),
            tenant_id=uuid4(),
            brand_id=uuid4(),
            entity_id=uuid4(),
            psp_connection_id="psp_stripe_001",
            event_type=EventType.DEPOSIT,
            event_timestamp=datetime.utcnow(),
            transaction_date=date.today(),
            amount_value=100000,
            amount_currency="USD",
            psp_transaction_id="txn_123",
            status=TransactionStatus.COMPLETED,
            reconciliation_status=ReconciliationStatus.PENDING,
            source_type="WEBHOOK",
            source_idempotency_key="test:123:DEPOSIT:1234567890"
        )
        
        assert transaction.amount_value == 100000
        assert transaction.amount_currency == "USD"
        assert transaction.event_type == EventType.DEPOSIT
        assert transaction.status == TransactionStatus.COMPLETED
    
    def test_transaction_validation(self):
        """Test transaction validation"""
        with pytest.raises(Exception):  # Pydantic validation error
            NormalizedTransaction(
                transaction_id=uuid4(),
                tenant_id=uuid4(),
                brand_id=uuid4(),
                entity_id=uuid4(),
                psp_connection_id="psp_stripe_001",
                event_type=EventType.DEPOSIT,
                event_timestamp=datetime.utcnow(),
                transaction_date=date.today(),
                amount_value=-100,  # Invalid: negative amount
                amount_currency="USD",
                psp_transaction_id="txn_123",
                status=TransactionStatus.COMPLETED,
                reconciliation_status=ReconciliationStatus.PENDING,
                source_type="WEBHOOK",
                source_idempotency_key="test:123:DEPOSIT:1234567890"
            )
    
    def test_transaction_serialization(self):
        """Test transaction JSON serialization"""
        transaction = NormalizedTransaction(
            transaction_id=uuid4(),
            tenant_id=uuid4(),
            brand_id=uuid4(),
            entity_id=uuid4(),
            psp_connection_id="psp_stripe_001",
            event_type=EventType.DEPOSIT,
            event_timestamp=datetime.utcnow(),
            transaction_date=date.today(),
            amount_value=100000,
            amount_currency="USD",
            psp_transaction_id="txn_123",
            status=TransactionStatus.COMPLETED,
            reconciliation_status=ReconciliationStatus.PENDING,
            source_type="WEBHOOK",
            source_idempotency_key="test:123:DEPOSIT:1234567890"
        )
        
        json_data = transaction.model_dump_json()
        assert json_data is not None
        assert "txn_123" in json_data


class TestPSPSettlement:
    """Test PSPSettlement model"""
    
    def test_create_settlement(self):
        """Test creating a PSP settlement"""
        settlement = PSPSettlement(
            settlement_id=uuid4(),
            tenant_id=uuid4(),
            psp_connection_id="psp_stripe_001",
            settlement_date=date.today(),
            settlement_batch_id="batch_001",
            settlement_line_number=1,
            amount_value=97100,
            amount_currency="USD",
            psp_transaction_ids=["txn_123"]
        )
        
        assert settlement.amount_value == 97100
        assert len(settlement.psp_transaction_ids) == 1


class TestReconciliationMatch:
    """Test ReconciliationMatch model"""
    
    def test_create_match(self):
        """Test creating a reconciliation match"""
        match = ReconciliationMatch(
            match_id=uuid4(),
            tenant_id=uuid4(),
            transaction_id=uuid4(),
            settlement_id=uuid4(),
            match_level=MatchLevel.STRONG_ID,
            confidence_score=Decimal("100.0"),
            match_method=MatchMethod.AUTO,
            matched_at=datetime.utcnow(),
            status=MatchStatus.MATCHED
        )
        
        assert match.match_level == MatchLevel.STRONG_ID
        assert match.confidence_score == Decimal("100.0")
        assert match.status == MatchStatus.MATCHED


class TestReconciliationException:
    """Test ReconciliationException model"""
    
    def test_create_exception(self):
        """Test creating a reconciliation exception"""
        exception = ReconciliationException(
            exception_id=uuid4(),
            tenant_id=uuid4(),
            transaction_id=uuid4(),
            exception_type=ExceptionType.UNMATCHED,
            amount_value=100000,
            amount_currency="USD",
            priority=ExceptionPriority.P1,
            status=ExceptionStatus.OPEN
        )
        
        assert exception.exception_type == ExceptionType.UNMATCHED
        assert exception.priority == ExceptionPriority.P1
        assert exception.amount_value == 100000


class TestLedgerEntry:
    """Test LedgerEntry model"""
    
    def test_create_ledger_entry(self):
        """Test creating a ledger entry"""
        entry = LedgerEntry(
            ledger_entry_id=uuid4(),
            tenant_id=uuid4(),
            entity_id=uuid4(),
            transaction_date=date.today(),
            account_debit="1001",
            account_credit="1100",
            amount=100000,
            currency="USD",
            description="Deposit transaction",
            posted_at=datetime.utcnow()
        )
        
        assert entry.account_debit == "1001"
        assert entry.account_credit == "1100"
        assert entry.amount == 100000


class TestChargeback:
    """Test Chargeback model"""
    
    def test_create_chargeback(self):
        """Test creating a chargeback"""
        chargeback = Chargeback(
            chargeback_id=uuid4(),
            tenant_id=uuid4(),
            transaction_id=uuid4(),
            psp_chargeback_id="cb_123",
            chargeback_amount=20000,
            chargeback_currency="USD",
            chargeback_date=date.today(),
            status=ChargebackStatus.INITIATED
        )
        
        assert chargeback.chargeback_amount == 20000
        assert chargeback.status == ChargebackStatus.INITIATED


class TestUser:
    """Test User model"""
    
    def test_create_user(self):
        """Test creating a user"""
        user = User(
            user_id=uuid4(),
            tenant_id=uuid4(),
            email="test@example.com",
            role=UserRole.FINANCE_MANAGER,
            status="ACTIVE"
        )
        
        assert user.email == "test@example.com"
        assert user.role == UserRole.FINANCE_MANAGER


class TestTenant:
    """Test Tenant models"""
    
    def test_create_tenant(self):
        """Test creating tenant hierarchy"""
        tenant = Tenant(
            tenant_id=uuid4(),
            tenant_name="Test Operator",
            tenant_code="TEST_OP"
        )
        
        brand = Brand(
            brand_id=uuid4(),
            tenant_id=tenant.tenant_id,
            brand_name="Test Brand",
            brand_code="TEST_BRAND"
        )
        
        entity = Entity(
            entity_id=uuid4(),
            brand_id=brand.brand_id,
            entity_name="Test Entity",
            entity_code="TEST_ENTITY",
            base_currency="USD"
        )
        
        assert tenant.tenant_code == "TEST_OP"
        assert brand.brand_code == "TEST_BRAND"
        assert entity.base_currency == "USD"


