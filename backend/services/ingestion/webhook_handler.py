"""
Webhook Ingestion Handler
Handles real-time webhook events from PSPs
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

import boto3
from fastapi import HTTPException, Request, Header
from pydantic import BaseModel

from shared.models.transaction import EventType

logger = logging.getLogger(__name__)

# AWS clients
secrets_manager = boto3.client('secretsmanager')
s3_client = boto3.client('s3')
kinesis_client = boto3.client('kinesis')


class WebhookEvent(BaseModel):
    """Raw webhook event from PSP"""
    event_id: str
    event_type: str
    data: Dict[str, Any]
    timestamp: Optional[datetime] = None


class WebhookHandler:
    """Handles webhook ingestion with idempotency and validation"""
    
    def __init__(
        self,
        s3_bucket: str,
        kinesis_stream: str,
        dynamodb_table: str = "idempotency_keys"
    ):
        self.s3_bucket = s3_bucket
        self.kinesis_stream = kinesis_stream
        self.dynamodb_table = dynamodb_table
        self.dynamodb = boto3.resource('dynamodb')
    
    async def handle_webhook(
        self,
        request: Request,
        tenant_id: UUID,
        psp_connection_id: str,
        x_signature: Optional[str] = Header(None, alias="X-Signature"),
        x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key")
    ) -> Dict[str, Any]:
        """
        Process incoming webhook event
        
        Steps:
        1. Validate webhook signature
        2. Check idempotency
        3. Store raw event in S3
        4. Publish to Kinesis stream
        """
        try:
            # Read request body
            body = await request.body()
            body_json = json.loads(body)
            
            # Get PSP connection config
            psp_config = await self._get_psp_config(tenant_id, psp_connection_id)
            
            # Validate signature
            if not await self._validate_signature(
                body, x_signature, psp_config
            ):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
            
            # Generate or use provided idempotency key
            idempotency_key = x_idempotency_key or self._generate_idempotency_key(
                psp_connection_id, body_json
            )
            
            # Check idempotency (DynamoDB)
            if await self._check_idempotency(tenant_id, idempotency_key):
                logger.info(f"Duplicate webhook detected: {idempotency_key}")
                return {"status": "duplicate", "idempotency_key": idempotency_key}
            
            # Store raw event in S3
            s3_path = await self._store_raw_event(
                tenant_id, psp_connection_id, body_json, idempotency_key
            )
            
            # Mark as processed in DynamoDB
            await self._mark_idempotent(tenant_id, idempotency_key, s3_path)
            
            # Publish to Kinesis stream
            await self._publish_to_kinesis(
                tenant_id, psp_connection_id, body_json, idempotency_key, s3_path
            )
            
            return {
                "status": "processed",
                "idempotency_key": idempotency_key,
                "s3_path": s3_path
            }
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")
    
    async def _validate_signature(
        self,
        body: bytes,
        signature: Optional[str],
        psp_config: Dict[str, Any]
    ) -> bool:
        """Validate webhook signature using HMAC"""
        if not signature:
            return False
        
        # Get webhook secret from Secrets Manager
        secret_arn = psp_config.get('webhook_signature_secret_arn')
        if not secret_arn:
            return False
        
        secret = secrets_manager.get_secret_value(SecretId=secret_arn)['SecretString']
        
        # Compute expected signature (HMAC-SHA256)
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (constant-time comparison)
        return hmac.compare_digest(signature, expected_signature)
    
    async def _check_idempotency(
        self,
        tenant_id: UUID,
        idempotency_key: str
    ) -> bool:
        """Check if event already processed (DynamoDB)"""
        table = self.dynamodb.Table(self.dynamodb_table)
        
        try:
            response = table.get_item(
                Key={'idempotency_key': idempotency_key}
            )
            return 'Item' in response
        except Exception as e:
            logger.error(f"Error checking idempotency: {str(e)}")
            return False
    
    async def _mark_idempotent(
        self,
        tenant_id: UUID,
        idempotency_key: str,
        s3_path: str
    ):
        """Mark event as processed in DynamoDB"""
        table = self.dynamodb.Table(self.dynamodb_table)
        
        # TTL: 7 days
        expires_at = int((datetime.utcnow().timestamp() + 7 * 24 * 60 * 60))
        
        table.put_item(
            Item={
                'idempotency_key': idempotency_key,
                'tenant_id': str(tenant_id),
                's3_path': s3_path,
                'processed_at': datetime.utcnow().isoformat(),
                'expires_at': expires_at
            }
        )
    
    async def _store_raw_event(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        event_data: Dict[str, Any],
        idempotency_key: str
    ) -> str:
        """Store raw event in S3"""
        # Partition by tenant/date
        date_str = datetime.utcnow().strftime('%Y/%m/%d')
        event_id = uuid4()
        s3_key = f"raw-events/{tenant_id}/{date_str}/{event_id}.json"
        
        # Upload to S3
        s3_client.put_object(
            Bucket=self.s3_bucket,
            Key=s3_key,
            Body=json.dumps(event_data, default=str),
            ContentType='application/json',
            ServerSideEncryption='AES256'
        )
        
        return f"s3://{self.s3_bucket}/{s3_key}"
    
    async def _publish_to_kinesis(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        event_data: Dict[str, Any],
        idempotency_key: str,
        s3_path: str
    ):
        """Publish event to Kinesis stream"""
        record = {
            'tenant_id': str(tenant_id),
            'psp_connection_id': psp_connection_id,
            'idempotency_key': idempotency_key,
            's3_path': s3_path,
            'event_data': event_data,
            'ingestion_timestamp': datetime.utcnow().isoformat(),
            'source_type': 'WEBHOOK'
        }
        
        # Partition key: tenant_id for even distribution
        kinesis_client.put_record(
            StreamName=self.kinesis_stream,
            Data=json.dumps(record),
            PartitionKey=str(tenant_id)
        )
    
    def _generate_idempotency_key(
        self,
        psp_connection_id: str,
        event_data: Dict[str, Any]
    ) -> str:
        """Generate idempotency key from event data"""
        event_id = event_data.get('id') or event_data.get('event_id', '')
        event_type = event_data.get('type') or event_data.get('event_type', '')
        timestamp = event_data.get('created') or event_data.get('timestamp', '')
        
        return f"{psp_connection_id}:{event_id}:{event_type}:{timestamp}"
    
    async def _get_psp_config(
        self,
        tenant_id: UUID,
        psp_connection_id: str
    ) -> Dict[str, Any]:
        """Get PSP connection configuration from database"""
        # TODO: Implement database lookup
        # This would query the psp_connection table
        return {}


