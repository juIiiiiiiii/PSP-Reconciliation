"""
Lambda Function: Kinesis Matching Consumer
Processes normalized events and matches them to settlements
"""

import json
import logging
import os
from typing import Dict, Any
from uuid import UUID

from backend.services.reconciliation.matching_engine import MatchingEngine

logger = logging.getLogger(__name__)

# Initialize service
matching_engine = MatchingEngine(
    db_connection_string=os.environ['DATABASE_URL']
)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for Kinesis matching consumer
    
    Processes normalized transactions:
    - Match against settlements
    - Create exceptions if unmatched
    - Trigger alerts if needed
    """
    processed_count = 0
    matched_count = 0
    exception_count = 0
    failed_count = 0
    
    for record in event['Records']:
        try:
            # Decode Kinesis record
            payload = json.loads(
                record['kinesis']['data'].decode('utf-8')
            )
            
            transaction_id = UUID(payload['transaction_id'])
            
            # Match transaction (Lambda doesn't support async, use sync wrapper)
            import asyncio
            result = asyncio.run(matching_engine.match_transaction(transaction_id))
            
            processed_count += 1
            
            if result.match and result.status.value == 'MATCHED':
                matched_count += 1
            elif result.exception:
                exception_count += 1
                # Trigger alert if high priority
                if result.exception.priority in ['P1', 'P2']:
                    # TODO: Trigger alert
                    pass
            
        except Exception as e:
            failed_count += 1
            logger.error(f"Error processing record: {str(e)}", exc_info=True)
    
    return {
        'statusCode': 200,
        'processed': processed_count,
        'matched': matched_count,
        'exceptions': exception_count,
        'failed': failed_count
    }

