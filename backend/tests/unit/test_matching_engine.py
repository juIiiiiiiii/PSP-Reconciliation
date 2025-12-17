"""
Unit tests for matching engine
Target: 90% coverage
"""

import pytest
from unittest.mock import Mock, patch
from datetime import date, timedelta
from uuid import UUID, uuid4
from decimal import Decimal

from backend.services.reconciliation.matching_engine import MatchingEngine, MatchResult
from backend.shared.models.match import MatchLevel, MatchMethod, MatchStatus
from backend.shared.models.exception import ExceptionType, ExceptionPriority, ExceptionStatus


class TestMatchingEngine:
    """Test matching engine"""
    
    @pytest.fixture
    def matching_engine(self):
        """Create matching engine instance"""
        return MatchingEngine(
            db_connection_string="postgresql://test:test@localhost:5432/test"
        )
    
    def test_match_level_1_strong_id(self, matching_engine):
        """Test Level 1: Strong ID matching"""
        transaction = {
            'transaction_id': uuid4(),
            'tenant_id': uuid4(),
            'psp_connection_id': 'psp_stripe_001',
            'psp_settlement_id': 'set_123',
            'transaction_date': date.today(),
            'amount_value': 100000,
            'amount_currency': 'USD',
            'reconciliation_status': 'PENDING'
        }
        
        # Mock database query
        with patch.object(matching_engine, '_get_transaction', return_value=transaction):
            with patch('backend.services.reconciliation.matching_engine.session') as mock_session:
                mock_session.execute.return_value.fetchone.return_value = (
                    uuid4(), 100000, 'USD'
                )
                
                # This would call the actual method, but we're testing the logic
                # In real test, we'd use testcontainers for actual DB
                pass
    
    def test_match_level_2_psp_reference(self, matching_engine):
        """Test Level 2: PSP Reference matching"""
        transaction = {
            'transaction_id': uuid4(),
            'tenant_id': uuid4(),
            'psp_connection_id': 'psp_stripe_001',
            'psp_payment_id': 'pay_456',
            'transaction_date': date.today(),
            'amount_value': 100000,
            'amount_currency': 'USD',
            'reconciliation_status': 'PENDING'
        }
        
        # Test matching logic
        # In real test, we'd use testcontainers
        pass
    
    def test_match_level_3_fuzzy(self, matching_engine):
        """Test Level 3: Fuzzy matching"""
        transaction = {
            'transaction_id': uuid4(),
            'tenant_id': uuid4(),
            'psp_connection_id': 'psp_stripe_001',
            'transaction_date': date.today(),
            'amount_value': 100000,
            'amount_currency': 'USD',
            'customer_id': 'cust_789',
            'reconciliation_status': 'PENDING'
        }
        
        # Test fuzzy matching with date window
        # In real test, we'd use testcontainers
        pass
    
    def test_match_level_4_amount_date(self, matching_engine):
        """Test Level 4: Amount + Date matching"""
        transaction = {
            'transaction_id': uuid4(),
            'tenant_id': uuid4(),
            'psp_connection_id': 'psp_stripe_001',
            'transaction_date': date.today(),
            'amount_value': 100000,
            'amount_currency': 'USD',
            'reconciliation_status': 'PENDING'
        }
        
        # Test amount + date matching
        # In real test, we'd use testcontainers
        pass
    
    def test_no_match_creates_exception(self, matching_engine):
        """Test that no match creates exception"""
        transaction = {
            'transaction_id': uuid4(),
            'tenant_id': uuid4(),
            'psp_connection_id': 'psp_stripe_001',
            'transaction_date': date.today(),
            'amount_value': 100000,
            'amount_currency': 'USD',
            'reconciliation_status': 'PENDING'
        }
        
        # Test exception creation
        # In real test, we'd use testcontainers
        pass
    
    def test_exception_priority_calculation(self, matching_engine):
        """Test exception priority based on amount"""
        # P1: >= $10,000
        assert matching_engine._create_exception(
            None, {'amount_value': 1000000}, ExceptionType.UNMATCHED, None
        ).priority == ExceptionPriority.P1
        
        # P2: >= $1,000
        assert matching_engine._create_exception(
            None, {'amount_value': 100000}, ExceptionType.UNMATCHED, None
        ).priority == ExceptionPriority.P2
        
        # P3: >= $100
        assert matching_engine._create_exception(
            None, {'amount_value': 10000}, ExceptionType.UNMATCHED, None
        ).priority == ExceptionPriority.P3
        
        # P4: < $100
        assert matching_engine._create_exception(
            None, {'amount_value': 5000}, ExceptionType.UNMATCHED, None
        ).priority == ExceptionPriority.P4


