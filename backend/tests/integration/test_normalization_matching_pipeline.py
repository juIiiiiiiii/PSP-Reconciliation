"""
Integration tests for normalization → matching pipeline
"""

import pytest
from unittest.mock import patch, AsyncMock
from uuid import UUID, uuid4
from datetime import date

from backend.services.normalization.normalizer import NormalizationService
from backend.services.reconciliation.matching_engine import MatchingEngine
from backend.shared.models.match import MatchStatus


@pytest.mark.asyncio
class TestNormalizationMatchingPipeline:
    """Test normalization to matching pipeline"""
    
    @pytest.fixture
    def normalizer(self):
        """Create normalizer"""
        return NormalizationService(
            db_connection_string="postgresql://test:test@localhost:5432/test",
            kinesis_stream="test-stream"
        )
    
    @pytest.fixture
    def matching_engine(self):
        """Create matching engine"""
        return MatchingEngine(
            db_connection_string="postgresql://test:test@localhost:5432/test"
        )
    
    async def test_normalized_event_to_matching(self, normalizer, matching_engine):
        """Test normalized event triggers matching"""
        # Mock normalized transaction
        normalized = type('obj', (object,), {
            'transaction_id': uuid4(),
            'tenant_id': uuid4(),
            'psp_connection_id': 'psp_stripe_001',
            'event_type': 'DEPOSIT',
            'transaction_date': date.today(),
            'amount_value': 100000,
            'amount_currency': 'USD',
            'psp_transaction_id': 'txn_123',
            'reconciliation_status': 'PENDING'
        })()
        
        # Mock matching
        with patch.object(matching_engine, 'match_transaction', new_callable=AsyncMock) as mock_match:
            mock_match.return_value = type('obj', (object,), {
                'status': 'MATCHED',
                'confidence': 100.0,
                'match': type('obj', (object,), {'match_id': uuid4()})()
            })()
            
            # Trigger matching
            result = await matching_engine.match_transaction(normalized.transaction_id)
            
            assert result.status.value == 'MATCHED'
            assert result.confidence == 100.0

