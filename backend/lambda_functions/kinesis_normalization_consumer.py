"""
Lambda Function: Kinesis Normalization Consumer
Processes raw events from Kinesis and normalizes them
"""

import json
import logging
import os
from typing import Dict, Any

from backend.services.normalization.normalizer import NormalizationService

logger = logging.getLogger(__name__)

# Initialize service
normalization_service = NormalizationService(
    db_connection_string=os.environ['DATABASE_URL'],
    kinesis_stream=os.environ['KINESIS_NORMALIZED_STREAM'],
    fx_rate_provider=os.environ.get('FX_RATE_PROVIDER', 'ECB')
)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for Kinesis normalization consumer
    
    Processes records from Kinesis stream:
    - Parse raw events
    - Normalize to canonical schema
    - Store in database
    - Publish to normalized-events stream
    """
    processed_count = 0
    failed_count = 0
    
    for record in event['Records']:
        try:
            # Decode Kinesis record
            payload = json.loads(
                record['kinesis']['data'].decode('utf-8')
            )
            
            # Normalize event (Lambda doesn't support async, use sync wrapper)
            import asyncio
            normalized = asyncio.run(normalization_service.normalize_event(payload))
            
            processed_count += 1
            logger.info(f"Normalized transaction: {normalized.transaction_id}")
            
        except Exception as e:
            failed_count += 1
            logger.error(f"Error processing record: {str(e)}", exc_info=True)
            
            # Send to Dead Letter Queue
            # TODO: Implement DLQ publishing
    
    return {
        'statusCode': 200,
        'processed': processed_count,
        'failed': failed_count
    }

