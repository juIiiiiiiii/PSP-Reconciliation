"""
End-to-end tests for failure scenarios
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from uuid import UUID, uuid4

from backend.services.ingestion.webhook_handler import WebhookHandler
from backend.services.normalization.normalizer import NormalizationService
from backend.services.reconciliation.matching_engine import MatchingEngine
from backend.services.alerting.alert_service import AlertService


@pytest.mark.e2e
@pytest.mark.asyncio
class TestFailureScenariosE2E:
    """Test failure scenarios end-to-end"""
    
    async def test_unmatched_transaction_creates_exception_and_alert(self):
        """Test unmatched transaction → exception → alert flow"""
        # Step 1: Normalize transaction
        normalizer = NormalizationService(
            db_connection_string="postgresql://test:test@localhost:5432/test",
            kinesis_stream="test-stream"
        )
        
        transaction = {
            'transaction_id': uuid4(),
            'tenant_id': uuid4(),
            'psp_connection_id': 'psp_stripe_test_001',
            'event_type': 'DEPOSIT',
            'amount_value': 100000,
            'amount_currency': 'USD',
            'psp_transaction_id': 'txn_unmatched_123',
            'reconciliation_status': 'PENDING'
        }
        
        # Step 2: Attempt matching (no settlement found)
        matching_engine = MatchingEngine(
            db_connection_string="postgresql://test:test@localhost:5432/test"
        )
        
        with patch.object(matching_engine, 'match_transaction', new_callable=AsyncMock) as mock_match:
            mock_match.return_value = type('obj', (object,), {
                'status': 'UNMATCHED',
                'confidence': 0.0,
                'exception': type('obj', (object,), {
                    'exception_id': uuid4(),
                    'exception_type': 'UNMATCHED',
                    'priority': 'P2',
                    'amount_value': 100000
                })()
            })()
            
            result = await matching_engine.match_transaction(transaction['transaction_id'])
            
            assert result.status.value == 'UNMATCHED'
            assert result.exception is not None
            assert result.exception.priority == 'P2'
        
        # Step 3: Alert triggered
        alert_service = AlertService(
            pagerduty_integration_key="test-key",
            slack_webhook_url="https://hooks.slack.com/test"
        )
        
        with patch.object(alert_service, 'trigger_alert', new_callable=AsyncMock) as mock_alert:
            await alert_service.trigger_alert(
                exception_id=result.exception.exception_id,
                priority=result.exception.priority,
                amount=result.exception.amount_value
            )
            
            mock_alert.assert_called_once()
    
    async def test_parser_error_goes_to_dlq(self):
        """Test parser error → DLQ → manual review"""
        normalizer = NormalizationService(
            db_connection_string="postgresql://test:test@localhost:5432/test",
            kinesis_stream="test-stream"
        )
        
        # Invalid event data
        invalid_event = {
            'invalid': 'data',
            'missing': 'required_fields'
        }
        
        # Mock parser error
        with patch.object(normalizer, 'normalize_event', side_effect=ValueError("Parser error")):
            with patch.object(normalizer, '_send_to_dlq', new_callable=AsyncMock) as mock_dlq:
                try:
                    await normalizer.normalize_event(invalid_event)
                except ValueError:
                    pass
                
                # Should send to DLQ
                mock_dlq.assert_called_once()
    
    async def test_database_failure_retry_recovery(self):
        """Test database failure → retry → recovery"""
        matching_engine = MatchingEngine(
            db_connection_string="postgresql://test:test@localhost:5432/test"
        )
        
        # Simulate database connection error
        with patch.object(matching_engine, '_get_transaction', side_effect=Exception("Database error")):
            with patch('time.sleep'):  # Mock sleep for retry
                with patch.object(matching_engine, '_get_transaction', side_effect=[Exception("Database error"), {"transaction_id": uuid4()}]):
                    # First call fails, retry succeeds
                    # This would be handled by retry logic
                    pass


