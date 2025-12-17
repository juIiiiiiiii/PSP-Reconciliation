"""
Integration tests for ingestion → normalization pipeline
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from uuid import UUID, uuid4

from backend.services.ingestion.webhook_handler import WebhookHandler
from backend.services.normalization.normalizer import NormalizationService


@pytest.mark.asyncio
class TestIngestionNormalizationPipeline:
    """Test ingestion to normalization pipeline"""
    
    @pytest.fixture
    def webhook_handler(self):
        """Create webhook handler"""
        return WebhookHandler(
            s3_bucket="test-bucket",
            kinesis_stream="test-stream"
        )
    
    @pytest.fixture
    def normalizer(self):
        """Create normalizer"""
        return NormalizationService(
            db_connection_string="postgresql://test:test@localhost:5432/test",
            kinesis_stream="test-stream"
        )
    
    async def test_webhook_to_normalization_flow(self, webhook_handler, normalizer):
        """Test complete webhook → normalization flow"""
        # Mock webhook event
        webhook_event = {
            'id': 'evt_test_123',
            'type': 'payment.succeeded',
            'data': {
                'object': {
                    'id': 'txn_test_123',
                    'amount': 1000.50,
                    'currency': 'usd',
                    'status': 'succeeded',
                    'created': 1705315800
                }
            }
        }
        
        # Mock idempotency check (not found)
        with patch.object(webhook_handler, '_check_idempotency', return_value=False):
            # Mock S3 storage
            with patch.object(webhook_handler, '_store_raw_event', return_value="s3://test/event.json"):
                # Mock Kinesis publish
                with patch.object(webhook_handler, '_publish_to_kinesis'):
                    # Mock normalization
                    with patch.object(normalizer, 'normalize_event', new_callable=AsyncMock) as mock_norm:
                        mock_norm.return_value = type('obj', (object,), {
                            'transaction_id': uuid4(),
                            'event_type': 'DEPOSIT',
                            'amount_value': 100050
                        })()
                        
                        # Process webhook
                        result = await webhook_handler.handle_webhook(
                            Mock(body=json.dumps(webhook_event).encode()),
                            uuid4(),
                            "psp_stripe_001"
                        )
                        
                        assert result['status'] == 'processed'
    
    async def test_idempotency_handling(self, webhook_handler):
        """Test idempotency prevents duplicate processing"""
        idempotency_key = "test:evt_123:payment.succeeded:1234567890"
        
        # First call: not found
        with patch.object(webhook_handler, '_check_idempotency', return_value=False):
            with patch.object(webhook_handler, '_store_raw_event', return_value="s3://test/event.json"):
                with patch.object(webhook_handler, '_publish_to_kinesis'):
                    result1 = await webhook_handler.handle_webhook(
                        Mock(body=b'{}', headers={'X-Idempotency-Key': idempotency_key}),
                        uuid4(),
                        "psp_stripe_001"
                    )
                    assert result1['status'] == 'processed'
        
        # Second call: found (duplicate)
        with patch.object(webhook_handler, '_check_idempotency', return_value=True):
            result2 = await webhook_handler.handle_webhook(
                Mock(body=b'{}', headers={'X-Idempotency-Key': idempotency_key}),
                uuid4(),
                "psp_stripe_001"
            )
            assert result2['status'] == 'duplicate'

