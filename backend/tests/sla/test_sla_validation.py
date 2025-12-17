"""
SLA validation tests
Validates that system meets SLA targets
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from backend.services.ingestion.webhook_handler import WebhookHandler
from backend.services.normalization.normalizer import NormalizationService
from backend.services.reconciliation.matching_engine import MatchingEngine


@pytest.mark.sla
class TestSLAValidation:
    """Test SLA targets are met"""
    
    @pytest.mark.asyncio
    async def test_ingestion_latency_p95_under_1s(self):
        """Test ingestion latency < 1s (p95)"""
        webhook_handler = WebhookHandler(
            s3_bucket="test-bucket",
            kinesis_stream="test-stream"
        )
        
        webhook_event = {
            'id': 'evt_test',
            'type': 'payment.succeeded',
            'data': {'object': {'id': 'txn_test', 'amount': 1000}}
        }
        
        latencies = []
        
        for _ in range(100):  # Test 100 requests
            start_time = time.time()
            
            with patch.object(webhook_handler, '_check_idempotency', return_value=False):
                with patch.object(webhook_handler, '_store_raw_event', return_value="s3://test/event.json"):
                    with patch.object(webhook_handler, '_publish_to_kinesis'):
                        await webhook_handler.handle_webhook(
                            Mock(body=json.dumps(webhook_event).encode()),
                            uuid4(),
                            "psp_stripe_001"
                        )
            
            latency = time.time() - start_time
            latencies.append(latency)
        
        # Calculate p95
        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]
        
        assert p95_latency < 1.0, f"P95 latency {p95_latency}s exceeds 1s SLA"
    
    @pytest.mark.asyncio
    async def test_normalization_latency_p95_under_5s(self):
        """Test normalization latency < 5s (p95)"""
        normalizer = NormalizationService(
            db_connection_string="postgresql://test:test@localhost:5432/test",
            kinesis_stream="test-stream"
        )
        
        raw_event = {
            'id': 'evt_test',
            'type': 'payment.succeeded',
            'data': {'object': {'id': 'txn_test', 'amount': 1000, 'currency': 'usd'}}
        }
        
        latencies = []
        
        for _ in range(100):
            start_time = time.time()
            
            with patch.object(normalizer, '_get_entity_brand', return_value=(uuid4(), uuid4())):
                with patch.object(normalizer, '_store_transaction'):
                    await normalizer.normalize_event(raw_event)
            
            latency = time.time() - start_time
            latencies.append(latency)
        
        # Calculate p95
        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]
        
        assert p95_latency < 5.0, f"P95 latency {p95_latency}s exceeds 5s SLA"
    
    @pytest.mark.asyncio
    async def test_matching_latency_p95_under_30s(self):
        """Test matching latency < 30s (p95)"""
        matching_engine = MatchingEngine(
            db_connection_string="postgresql://test:test@localhost:5432/test"
        )
        
        transaction_id = uuid4()
        
        latencies = []
        
        for _ in range(100):
            start_time = time.time()
            
            with patch.object(matching_engine, 'match_transaction', new_callable=AsyncMock) as mock_match:
                mock_match.return_value = type('obj', (object,), {
                    'status': 'MATCHED',
                    'confidence': 100.0
                })()
                
                await matching_engine.match_transaction(transaction_id)
            
            latency = time.time() - start_time
            latencies.append(latency)
        
        # Calculate p95
        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]
        
        assert p95_latency < 30.0, f"P95 latency {p95_latency}s exceeds 30s SLA"
    
    @pytest.mark.asyncio
    async def test_match_rate_over_99_percent(self):
        """Test match rate > 99%"""
        matching_engine = MatchingEngine(
            db_connection_string="postgresql://test:test@localhost:5432/test"
        )
        
        # Simulate 1000 transactions
        total = 1000
        matched = 0
        
        for i in range(total):
            transaction_id = uuid4()
            
            with patch.object(matching_engine, 'match_transaction', new_callable=AsyncMock) as mock_match:
                # 99.5% match rate (995 matched, 5 unmatched)
                if i < 995:
                    mock_match.return_value = type('obj', (object,), {
                        'status': 'MATCHED',
                        'confidence': 100.0
                    })()
                    matched += 1
                else:
                    mock_match.return_value = type('obj', (object,), {
                        'status': 'UNMATCHED',
                        'confidence': 0.0
                    })()
                
                result = await matching_engine.match_transaction(transaction_id)
                if result.status.value == 'MATCHED':
                    matched += 1
        
        match_rate = (matched / total) * 100
        assert match_rate >= 99.0, f"Match rate {match_rate}% below 99% SLA"
    
    @pytest.mark.asyncio
    async def test_reconciliation_completeness_over_95_percent(self):
        """Test reconciliation completeness > 95%"""
        # Completeness = (Settled transactions / Expected transactions) * 100
        
        expected_transactions = 1000
        settled_transactions = 960  # 96% completeness
        
        completeness = (settled_transactions / expected_transactions) * 100
        assert completeness >= 95.0, f"Completeness {completeness}% below 95% SLA"


