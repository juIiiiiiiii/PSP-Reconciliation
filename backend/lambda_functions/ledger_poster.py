"""
Lambda Function: Ledger Poster
Posts matched transactions to ledger
"""

import json
import logging
import os
from typing import Dict, Any
from uuid import UUID

from backend.services.ledger.ledger_service import LedgerService

logger = logging.getLogger(__name__)

# Initialize service
ledger_service = LedgerService(
    db_connection_string=os.environ['DATABASE_URL']
)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for ledger posting
    
    Processes matched transactions:
    - Generate double-entry ledger entries
    - Post to ledger
    - Update transaction status
    """
    processed_count = 0
    posted_count = 0
    failed_count = 0
    
    for record in event['Records']:
        try:
            # Decode record (could be from Kinesis, SQS, or direct invocation)
            if 'kinesis' in record:
                payload = json.loads(record['kinesis']['data'].decode('utf-8'))
            elif 'body' in record:
                payload = json.loads(record['body'])
            else:
                payload = record
            
            transaction_id = UUID(payload['transaction_id'])
            match_id = UUID(payload['match_id'])
            
            # Post to ledger (Lambda doesn't support async, use sync wrapper)
            import asyncio
            entries = asyncio.run(ledger_service.post_matched_transaction(
                transaction_id, match_id
            ))
            
            processed_count += 1
            posted_count += len(entries)
            
        except Exception as e:
            failed_count += 1
            logger.error(f"Error posting to ledger: {str(e)}", exc_info=True)
    
    return {
        'statusCode': 200,
        'processed': processed_count,
        'posted': posted_count,
        'failed': failed_count
    }

