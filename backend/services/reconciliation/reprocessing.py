"""
Reprocessing Service - Handles reprocessing and backfills
"""

import logging
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from services.reconciliation.matching_engine import MatchingEngine

logger = logging.getLogger(__name__)


class ReprocessingService:
    """Handles reprocessing of transactions and backfills"""
    
    def __init__(self, db_connection_string: str):
        self.db_engine = create_engine(db_connection_string)
        self.SessionLocal = sessionmaker(bind=self.db_engine)
        self.matching_engine = MatchingEngine(db_connection_string)
    
    async def reprocess_date_range(
        self,
        tenant_id: UUID,
        start_date: date,
        end_date: date,
        psp_connection_id: Optional[str] = None
    ) -> dict:
        """
        Reprocess transactions for a date range
        
        Steps:
        1. Mark existing matches as REPROCESSING
        2. Re-run matching for all transactions in range
        3. Compare results and create audit log for changes
        4. Update matches
        """
        with self.SessionLocal() as session:
            # Get transactions in range
            query = """
                SELECT transaction_id
                FROM normalized_transaction
                WHERE tenant_id = :tenant_id
                AND transaction_date BETWEEN :start_date AND :end_date
                AND reconciliation_status IN ('PENDING', 'UNMATCHED', 'PARTIAL_MATCH')
            """
            params = {
                'tenant_id': str(tenant_id),
                'start_date': start_date,
                'end_date': end_date
            }
            
            if psp_connection_id:
                query += " AND psp_connection_id = :psp_conn"
                params['psp_conn'] = psp_connection_id
            
            transactions = session.execute(text(query), params).fetchall()
            
            processed = 0
            matched = 0
            exceptions = 0
            
            for (transaction_id,) in transactions:
                try:
                    # Re-run matching
                    result = await self.matching_engine.match_transaction(
                        UUID(transaction_id)
                    )
                    
                    processed += 1
                    if result.match and result.status.value == 'MATCHED':
                        matched += 1
                    if result.exception:
                        exceptions += 1
                        
                except Exception as e:
                    logger.error(f"Error reprocessing transaction {transaction_id}: {str(e)}")
            
            return {
                'status': 'completed',
                'processed_count': processed,
                'matched_count': matched,
                'exceptions_count': exceptions,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
    
    async def backfill_historical(
        self,
        tenant_id: UUID,
        start_date: date,
        end_date: date,
        batch_size: int = 1000
    ) -> dict:
        """
        Backfill historical transactions
        
        Processes in batches to avoid overwhelming the system
        """
        current_date = start_date
        total_processed = 0
        total_matched = 0
        
        while current_date <= end_date:
            batch_end = min(
                date(current_date.year, current_date.month, 28),  # End of month
                end_date
            )
            
            result = await self.reprocess_date_range(
                tenant_id, current_date, batch_end
            )
            
            total_processed += result['processed_count']
            total_matched += result['matched_count']
            
            # Move to next month
            if batch_end.month == 12:
                current_date = date(batch_end.year + 1, 1, 1)
            else:
                current_date = date(batch_end.year, batch_end.month + 1, 1)
        
        return {
            'status': 'completed',
            'total_processed': total_processed,
            'total_matched': total_matched,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }


