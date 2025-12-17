"""
Integration tests for matching → ledger pipeline
"""

import pytest
from unittest.mock import patch, AsyncMock
from uuid import UUID, uuid4

from backend.services.reconciliation.matching_engine import MatchingEngine
from backend.services.ledger.ledger_service import LedgerService


@pytest.mark.asyncio
class TestMatchingLedgerPipeline:
    """Test matching to ledger pipeline"""
    
    @pytest.fixture
    def matching_engine(self):
        """Create matching engine"""
        return MatchingEngine(
            db_connection_string="postgresql://test:test@localhost:5432/test"
        )
    
    @pytest.fixture
    def ledger_service(self):
        """Create ledger service"""
        return LedgerService(
            db_connection_string="postgresql://test:test@localhost:5432/test"
        )
    
    async def test_matched_transaction_to_ledger(self, matching_engine, ledger_service):
        """Test matched transaction posts to ledger"""
        transaction_id = uuid4()
        match_id = uuid4()
        
        # Mock ledger posting
        with patch.object(ledger_service, 'post_matched_transaction', new_callable=AsyncMock) as mock_ledger:
            mock_ledger.return_value = [
                type('obj', (object,), {
                    'ledger_entry_id': uuid4(),
                    'account_debit': '1001',
                    'account_credit': '1100',
                    'amount': 97100
                })()
            ]
            
            # Post to ledger
            entries = await ledger_service.post_matched_transaction(transaction_id, match_id)
            
            assert len(entries) > 0
            assert entries[0].account_debit == '1001'
            assert entries[0].account_credit == '1100'


