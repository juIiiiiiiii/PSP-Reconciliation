"""
Unit tests for ledger service
Target: 85% coverage
"""

import pytest
from unittest.mock import Mock, patch
from datetime import date
from uuid import UUID, uuid4

from backend.services.ledger.ledger_service import LedgerService, ChartOfAccounts
from backend.shared.models.ledger import LedgerEntry


class TestChartOfAccounts:
    """Test chart of accounts"""
    
    def test_get_cash_account(self):
        """Test getting cash account for PSP and currency"""
        assert ChartOfAccounts.get_cash_account("psp_stripe_us_001", "USD") == ChartOfAccounts.CASH_STRIPE_USD
        assert ChartOfAccounts.get_cash_account("psp_adyen_eu_001", "EUR") == ChartOfAccounts.CASH_ADYEN_EUR
        assert ChartOfAccounts.get_cash_account("psp_paypal_uk_001", "GBP") == ChartOfAccounts.CASH_PAYPAL_GBP


class TestLedgerService:
    """Test ledger service"""
    
    @pytest.fixture
    def ledger_service(self):
        """Create ledger service instance"""
        return LedgerService(
            db_connection_string="postgresql://test:test@localhost:5432/test"
        )
    
    @pytest.mark.asyncio
    async def test_post_deposit(self, ledger_service):
        """Test posting deposit transaction"""
        transaction = {
            'transaction_id': uuid4(),
            'tenant_id': uuid4(),
            'entity_id': uuid4(),
            'psp_connection_id': 'psp_stripe_us_001',
            'event_type': 'DEPOSIT',
            'transaction_date': date.today(),
            'amount_value': 100000,  # $1000
            'amount_currency': 'USD',
            'psp_fee': 2900,  # $29
            'net_amount': 97100,  # $971
            'psp_transaction_id': 'txn_123'
        }
        match = {
            'match_id': uuid4(),
            'transaction_id': transaction['transaction_id'],
            'settlement_id': uuid4()
        }
        
        # Mock database operations
        with patch.object(ledger_service, '_get_transaction', return_value=transaction):
            with patch.object(ledger_service, '_get_match', return_value=match):
                with patch('backend.services.ledger.ledger_service.session') as mock_session:
                    entries = await ledger_service._post_deposit(
                        mock_session, transaction, match
                    )
                    
                    # Should create 2 entries:
                    # 1. Debit Cash, Credit Accounts Receivable (net amount)
                    # 2. Debit PSP Fees, Credit Cash (fee)
                    assert len(entries) == 2
                    assert entries[0].account_debit == ChartOfAccounts.CASH_STRIPE_USD
                    assert entries[0].account_credit == ChartOfAccounts.ACCOUNTS_RECEIVABLE
                    assert entries[1].account_debit == ChartOfAccounts.PSP_FEES
    
    @pytest.mark.asyncio
    async def test_post_withdrawal(self, ledger_service):
        """Test posting withdrawal transaction"""
        transaction = {
            'transaction_id': uuid4(),
            'tenant_id': uuid4(),
            'entity_id': uuid4(),
            'psp_connection_id': 'psp_stripe_us_001',
            'event_type': 'WITHDRAWAL',
            'transaction_date': date.today(),
            'amount_value': 50000,  # $500
            'amount_currency': 'USD',
            'psp_transaction_id': 'txn_456'
        }
        match = {
            'match_id': uuid4(),
            'transaction_id': transaction['transaction_id'],
            'settlement_id': uuid4()
        }
        
        with patch.object(ledger_service, '_get_transaction', return_value=transaction):
            with patch.object(ledger_service, '_get_match', return_value=match):
                with patch('backend.services.ledger.ledger_service.session') as mock_session:
                    entries = await ledger_service._post_withdrawal(
                        mock_session, transaction, match
                    )
                    
                    # Should create 1 entry: Debit Player Balances, Credit Cash
                    assert len(entries) == 1
                    assert entries[0].account_debit == ChartOfAccounts.PLAYER_BALANCES
                    assert entries[0].account_credit == ChartOfAccounts.CASH_STRIPE_USD
    
    @pytest.mark.asyncio
    async def test_post_refund(self, ledger_service):
        """Test posting refund transaction"""
        transaction = {
            'transaction_id': uuid4(),
            'tenant_id': uuid4(),
            'entity_id': uuid4(),
            'psp_connection_id': 'psp_stripe_us_001',
            'event_type': 'REFUND',
            'transaction_date': date.today(),
            'amount_value': 30000,  # $300
            'amount_currency': 'USD',
            'psp_transaction_id': 'txn_789'
        }
        match = {
            'match_id': uuid4(),
            'transaction_id': transaction['transaction_id'],
            'settlement_id': uuid4()
        }
        
        with patch.object(ledger_service, '_get_transaction', return_value=transaction):
            with patch.object(ledger_service, '_get_match', return_value=match):
                with patch('backend.services.ledger.ledger_service.session') as mock_session:
                    entries = await ledger_service._post_refund(
                        mock_session, transaction, match
                    )
                    
                    # Should create 1 entry: Debit Accounts Receivable, Credit Cash
                    assert len(entries) == 1
                    assert entries[0].account_debit == ChartOfAccounts.ACCOUNTS_RECEIVABLE
                    assert entries[0].account_credit == ChartOfAccounts.CASH_STRIPE_USD
    
    @pytest.mark.asyncio
    async def test_post_chargeback(self, ledger_service):
        """Test posting chargeback transaction"""
        transaction = {
            'transaction_id': uuid4(),
            'tenant_id': uuid4(),
            'entity_id': uuid4(),
            'psp_connection_id': 'psp_stripe_us_001',
            'event_type': 'CHARGEBACK',
            'transaction_date': date.today(),
            'amount_value': 20000,  # $200
            'amount_currency': 'USD',
            'psp_transaction_id': 'txn_cb_123'
        }
        match = {
            'match_id': uuid4(),
            'transaction_id': transaction['transaction_id'],
            'settlement_id': uuid4()
        }
        
        with patch.object(ledger_service, '_get_transaction', return_value=transaction):
            with patch.object(ledger_service, '_get_match', return_value=match):
                with patch('backend.services.ledger.ledger_service.session') as mock_session:
                    entries = await ledger_service._post_chargeback(
                        mock_session, transaction, match
                    )
                    
                    # Should create 2 entries:
                    # 1. Debit Chargeback Losses, Credit Cash
                    # 2. Debit Accounts Receivable (reversal), Credit Accounts Receivable
                    assert len(entries) == 2
                    assert entries[0].account_debit == ChartOfAccounts.CHARGEBACK_LOSSES
                    assert entries[1].account_debit == ChartOfAccounts.ACCOUNTS_RECEIVABLE
                    assert entries[1].account_credit == ChartOfAccounts.ACCOUNTS_RECEIVABLE


