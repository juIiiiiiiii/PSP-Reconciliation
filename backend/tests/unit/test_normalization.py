"""
Unit tests for normalization service
Target: 90% coverage
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, date
from uuid import UUID, uuid4

from backend.services.normalization.normalizer import NormalizationService
from backend.shared.models.transaction import EventType, TransactionStatus, ReconciliationStatus


class TestNormalizationService:
    """Test normalization service"""
    
    @pytest.fixture
    def normalizer(self):
        """Create normalization service instance"""
        return NormalizationService(
            db_connection_string="postgresql://test:test@localhost:5432/test",
            kinesis_stream="test-stream"
        )
    
    def test_map_event_type(self, normalizer):
        """Test event type mapping"""
        assert normalizer._map_event_type("DEPOSIT") == EventType.DEPOSIT
        assert normalizer._map_event_type("WITHDRAWAL") == EventType.WITHDRAWAL
        assert normalizer._map_event_type("REFUND") == EventType.REFUND
        assert normalizer._map_event_type("CHARGEBACK") == EventType.CHARGEBACK
    
    def test_map_status(self, normalizer):
        """Test status mapping"""
        assert normalizer._map_status("completed") == TransactionStatus.COMPLETED
        assert normalizer._map_status("succeeded") == TransactionStatus.COMPLETED
        assert normalizer._map_status("pending") == TransactionStatus.PENDING
        assert normalizer._map_status("failed") == TransactionStatus.FAILED
    
    def test_parse_timestamp(self, normalizer):
        """Test timestamp parsing"""
        # ISO format
        dt = normalizer._parse_timestamp("2024-01-15T10:30:00Z")
        assert isinstance(dt, datetime)
        
        # Unix timestamp
        dt = normalizer._parse_timestamp(1705315800)
        assert isinstance(dt, datetime)
        
        # Already datetime
        now = datetime.utcnow()
        dt = normalizer._parse_timestamp(now)
        assert dt == now
    
    def test_parse_date(self, normalizer):
        """Test date parsing"""
        # From date string
        d = normalizer._parse_date("2024-01-15")
        assert isinstance(d, date)
        assert d.year == 2024
        assert d.month == 1
        assert d.day == 15
        
        # From datetime
        dt = datetime(2024, 1, 15, 10, 30, 0)
        d = normalizer._parse_date(dt)
        assert d == date(2024, 1, 15)
        
        # Already date
        today = date.today()
        d = normalizer._parse_date(today)
        assert d == today
    
    @pytest.mark.asyncio
    async def test_enrich_fx_no_conversion_needed(self, normalizer):
        """Test FX enrichment when no conversion needed"""
        event = {
            'currency': 'USD',
            'amount': 100000
        }
        psp_config = {
            'base_currency': 'USD'
        }
        
        enriched = await normalizer._enrich_fx(event, psp_config)
        
        assert enriched['currency'] == 'USD'
        assert 'fx_rate' not in enriched
    
    @pytest.mark.asyncio
    async def test_enrich_fx_with_conversion(self, normalizer):
        """Test FX enrichment with currency conversion"""
        event = {
            'currency': 'EUR',
            'amount': 100000,
            'transaction_date': date(2024, 1, 15)
        }
        psp_config = {
            'base_currency': 'USD'
        }
        
        # Mock FX rate lookup
        with patch.object(normalizer, '_get_fx_rate', new_callable=AsyncMock) as mock_fx:
            mock_fx.return_value = {
                'rate': 1.0850,
                'source': 'ECB',
                'date': date(2024, 1, 15)
            }
            
            enriched = await normalizer._enrich_fx(event, psp_config)
            
            assert enriched['fx_rate'] == 1.0850
            assert enriched['original_currency'] == 'EUR'
            assert enriched['currency'] == 'USD'
            assert enriched['amount'] == int(100000 * 1.0850)
    
    @pytest.mark.asyncio
    async def test_map_to_canonical(self, normalizer):
        """Test mapping to canonical schema"""
        event = {
            'psp_transaction_id': 'txn_123',
            'psp_payment_id': 'pay_456',
            'amount': 100000,
            'currency': 'USD',
            'fee': 2900,
            'net': 97100,
            'status': 'completed',
            'created': '2024-01-15T10:30:00Z',
            'customer_id': 'cust_789'
        }
        raw_event = {
            'tenant_id': str(uuid4()),
            'psp_connection_id': 'psp_stripe_001',
            'source_type': 'WEBHOOK',
            'idempotency_key': 'test:123:DEPOSIT:1234567890'
        }
        
        # Mock entity/brand lookup
        with patch.object(normalizer, '_get_entity_brand', new_callable=AsyncMock) as mock_entity:
            mock_entity.return_value = (uuid4(), uuid4())
            
            normalized = await normalizer._map_to_canonical(
                UUID(raw_event['tenant_id']),
                raw_event['psp_connection_id'],
                event,
                raw_event
            )
            
            assert normalized.amount_value == 100000
            assert normalized.amount_currency == 'USD'
            assert normalized.psp_transaction_id == 'txn_123'
            assert normalized.psp_payment_id == 'pay_456'
            assert normalized.psp_fee == 2900
            assert normalized.net_amount == 97100
            assert normalized.status == TransactionStatus.COMPLETED


