"""
API Polling Connector - Polls PSP APIs for new transactions
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID

import aiohttp
import boto3

from services.ingestion.webhook_handler import WebhookHandler

logger = logging.getLogger(__name__)

secrets_manager = boto3.client('secretsmanager')
kinesis_client = boto3.client('kinesis')


class APIPoller:
    """Polls PSP APIs for incremental transaction sync"""
    
    def __init__(
        self,
        kinesis_stream: str,
        poll_interval_minutes: int = 15
    ):
        self.kinesis_stream = kinesis_stream
        self.poll_interval_minutes = poll_interval_minutes
    
    async def poll_psp(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        psp_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Poll PSP API for new transactions
        
        Steps:
        1. Get last sync timestamp
        2. Call PSP API with since parameter
        3. Process each transaction
        4. Update last sync timestamp
        """
        try:
            # Get last sync timestamp (from database or cache)
            last_sync = await self._get_last_sync(tenant_id, psp_connection_id)
            since = last_sync or (datetime.utcnow() - timedelta(days=1))
            
            # Get API credentials
            api_key = await self._get_api_key(psp_config)
            
            # Call PSP API
            transactions = await self._fetch_transactions(
                psp_config, api_key, since
            )
            
            # Process each transaction
            processed_count = 0
            for transaction in transactions:
                await self._process_transaction(
                    tenant_id, psp_connection_id, transaction
                )
                processed_count += 1
            
            # Update last sync timestamp
            await self._update_last_sync(tenant_id, psp_connection_id, datetime.utcnow())
            
            return {
                "status": "completed",
                "transactions_fetched": len(transactions),
                "transactions_processed": processed_count
            }
            
        except Exception as e:
            logger.error(f"Error polling PSP API: {str(e)}", exc_info=True)
            raise
    
    async def _fetch_transactions(
        self,
        psp_config: Dict[str, Any],
        api_key: str,
        since: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch transactions from PSP API"""
        endpoint = psp_config.get('endpoint_url')
        if not endpoint:
            raise ValueError("No endpoint URL configured")
        
        # Build request
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'since': since.isoformat(),
            'limit': 100  # Pagination
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, headers=headers, params=params) as response:
                if response.status == 429:  # Rate limit
                    await asyncio.sleep(60)  # Wait 1 minute
                    return await self._fetch_transactions(psp_config, api_key, since)
                
                response.raise_for_status()
                data = await response.json()
                
                # Handle pagination if needed
                transactions = data.get('data', [])
                
                # If has_more, fetch next page
                if data.get('has_more'):
                    next_page = await self._fetch_next_page(
                        psp_config, api_key, data.get('next_cursor')
                    )
                    transactions.extend(next_page)
                
                return transactions
    
    async def _fetch_next_page(
        self,
        psp_config: Dict[str, Any],
        api_key: str,
        cursor: str
    ) -> List[Dict[str, Any]]:
        """Fetch next page of results"""
        # Similar to _fetch_transactions but with cursor
        pass
    
    async def _process_transaction(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        transaction: Dict[str, Any]
    ):
        """Process single transaction (similar to webhook handler)"""
        # Generate idempotency key
        idempotency_key = f"{psp_connection_id}:{transaction.get('id')}:{transaction.get('type')}:{transaction.get('created')}"
        
        # Publish to Kinesis
        record = {
            'tenant_id': str(tenant_id),
            'psp_connection_id': psp_connection_id,
            'idempotency_key': idempotency_key,
            'event_data': transaction,
            'ingestion_timestamp': datetime.utcnow().isoformat(),
            'source_type': 'API_POLLING'
        }
        
        kinesis_client.put_record(
            StreamName=self.kinesis_stream,
            Data=json.dumps(record),
            PartitionKey=str(tenant_id)
        )
    
    async def _get_api_key(self, psp_config: Dict[str, Any]) -> str:
        """Get API key from Secrets Manager"""
        secret_arn = psp_config.get('authentication_secret_arn')
        if not secret_arn:
            raise ValueError("No API key secret configured")
        
        secret = secrets_manager.get_secret_value(SecretId=secret_arn)
        return secret['SecretString']
    
    async def _get_last_sync(
        self,
        tenant_id: UUID,
        psp_connection_id: str
    ) -> Optional[datetime]:
        """Get last sync timestamp from database"""
        # TODO: Implement database lookup
        return None
    
    async def _update_last_sync(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        timestamp: datetime
    ):
        """Update last sync timestamp in database"""
        # TODO: Implement database update
        pass

