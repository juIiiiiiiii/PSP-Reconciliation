"""
Normalization Service
Transforms raw PSP events into canonical normalized transaction format
"""

import json
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, Optional
from uuid import UUID, uuid4

import boto3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from shared.models.transaction import (
    NormalizedTransaction,
    EventType,
    TransactionStatus,
    ReconciliationStatus
)

logger = logging.getLogger(__name__)

kinesis_client = boto3.client('kinesis')
secrets_manager = boto3.client('secretsmanager')


class NormalizationService:
    """Normalizes raw events to canonical schema"""
    
    def __init__(
        self,
        db_connection_string: str,
        kinesis_stream: str,
        fx_rate_provider: Optional[str] = None
    ):
        self.db_engine = create_engine(db_connection_string)
        self.SessionLocal = sessionmaker(bind=self.db_engine)
        self.kinesis_stream = kinesis_stream
        self.fx_rate_provider = fx_rate_provider or "ECB"
    
    async def normalize_event(
        self,
        raw_event: Dict[str, Any]
    ) -> NormalizedTransaction:
        """
        Normalize raw event to canonical schema
        
        Steps:
        1. Extract tenant and PSP connection info
        2. Parse event data based on PSP parser
        3. Enrich with FX rates if needed
        4. Map to canonical schema
        5. Store in database (idempotent)
        6. Publish to Kinesis for matching
        """
        try:
            tenant_id = UUID(raw_event['tenant_id'])
            psp_connection_id = raw_event['psp_connection_id']
            event_data = raw_event['event_data']
            
            # Get PSP connection config
            psp_config = await self._get_psp_config(tenant_id, psp_connection_id)
            
            # Parse event based on PSP
            parsed_event = await self._parse_event(event_data, psp_config)
            
            # Enrich with FX rates
            enriched_event = await self._enrich_fx(parsed_event, psp_config)
            
            # Map to canonical schema
            normalized = await self._map_to_canonical(
                tenant_id, psp_connection_id, enriched_event, raw_event
            )
            
            # Store in database (idempotent upsert)
            stored = await self._store_normalized(normalized)
            
            # Publish to Kinesis for matching
            await self._publish_to_matching(stored)
            
            return stored
            
        except Exception as e:
            logger.error(f"Error normalizing event: {str(e)}", exc_info=True)
            raise
    
    async def _parse_event(
        self,
        event_data: Dict[str, Any],
        psp_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse event based on PSP-specific format"""
        # This would use the parser framework
        # For now, assume event_data is already parsed
        return event_data
    
    async def _enrich_fx(
        self,
        event: Dict[str, Any],
        psp_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrich event with FX rates if currency conversion needed"""
        amount_currency = event.get('currency') or event.get('amount_currency')
        entity_base_currency = psp_config.get('base_currency')
        
        if amount_currency and entity_base_currency and amount_currency != entity_base_currency:
            # Get FX rate
            fx_rate = await self._get_fx_rate(
                amount_currency, entity_base_currency, event.get('transaction_date')
            )
            
            if fx_rate:
                event['fx_rate'] = float(fx_rate['rate'])
                event['fx_rate_source'] = fx_rate['source']
                event['fx_rate_date'] = fx_rate['date']
                event['original_currency'] = amount_currency
                # Convert amount to base currency
                original_amount = event.get('amount', 0)
                event['amount'] = int(original_amount * fx_rate['rate'])
                event['currency'] = entity_base_currency
        
        return event
    
    async def _get_fx_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """Get FX rate from database or external provider"""
        if not rate_date:
            rate_date = date.today()
        
        # Try database first
        with self.SessionLocal() as session:
            result = session.execute(
                text("""
                    SELECT rate, rate_source, rate_date
                    FROM fx_rate
                    WHERE from_currency = :from_curr
                    AND to_currency = :to_curr
                    AND rate_date = :date
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {
                    'from_curr': from_currency,
                    'to_curr': to_currency,
                    'date': rate_date
                }
            ).fetchone()
            
            if result:
                return {
                    'rate': float(result[0]),
                    'source': result[1],
                    'date': result[2]
                }
        
        # If not in database, fetch from external provider
        # TODO: Implement external FX provider integration
        return None
    
    async def _map_to_canonical(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        event: Dict[str, Any],
        raw_event: Dict[str, Any]
    ) -> NormalizedTransaction:
        """Map parsed event to canonical NormalizedTransaction schema"""
        
        # Extract entity/brand from PSP connection
        entity_id, brand_id = await self._get_entity_brand(tenant_id, psp_connection_id)
        
        # Map event type
        event_type = self._map_event_type(event.get('event_type', ''))
        
        # Parse timestamps
        event_timestamp = self._parse_timestamp(event.get('created') or event.get('event_date'))
        transaction_date = self._parse_date(event.get('transaction_date') or event_timestamp.date())
        
        # Extract amounts
        amount_value = event.get('amount', 0)
        if isinstance(amount_value, float):
            amount_value = int(amount_value * 100)  # Convert to cents
        
        amount_currency = event.get('currency', 'USD')
        
        # Extract fees
        psp_fee = event.get('fee', 0)
        if isinstance(psp_fee, float):
            psp_fee = int(psp_fee * 100)
        
        net_amount = event.get('net', amount_value - psp_fee)
        if isinstance(net_amount, float):
            net_amount = int(net_amount * 100)
        
        return NormalizedTransaction(
            transaction_id=uuid4(),
            tenant_id=tenant_id,
            brand_id=brand_id,
            entity_id=entity_id,
            psp_connection_id=psp_connection_id,
            event_type=event_type,
            event_timestamp=event_timestamp,
            transaction_date=transaction_date,
            amount_value=amount_value,
            amount_currency=amount_currency,
            amount_original_currency=event.get('original_currency'),
            amount_fx_rate=Decimal(str(event.get('fx_rate'))) if event.get('fx_rate') else None,
            amount_fx_rate_source=event.get('fx_rate_source'),
            amount_fx_rate_date=event.get('fx_rate_date'),
            psp_transaction_id=event.get('psp_transaction_id') or event.get('psp_event_id', ''),
            psp_payment_id=event.get('psp_payment_id'),
            psp_settlement_id=event.get('psp_settlement_id'),
            psp_batch_id=event.get('psp_batch_id'),
            customer_id=event.get('customer_id'),
            player_id=event.get('player_id'),
            game_session_id=event.get('game_session_id'),
            psp_fee=psp_fee if psp_fee > 0 else None,
            fx_fee=None,  # TODO: Calculate FX fees
            net_amount=net_amount,
            status=self._map_status(event.get('status', 'completed')),
            reconciliation_status=ReconciliationStatus.PENDING,
            source_type=raw_event.get('source_type', 'WEBHOOK'),
            source_idempotency_key=raw_event.get('idempotency_key', ''),
            source_raw_event_id=UUID(raw_event.get('raw_event_id')) if raw_event.get('raw_event_id') else None,
            source_raw_event_s3_path=raw_event.get('s3_path'),
            metadata=event.get('metadata', {}),
            version=1,
            schema_version=1
        )
    
    async def _store_normalized(
        self,
        normalized: NormalizedTransaction
    ) -> NormalizedTransaction:
        """Store normalized transaction in database (idempotent)"""
        with self.SessionLocal() as session:
            # Check if exists (idempotency)
            existing = session.execute(
                text("""
                    SELECT transaction_id
                    FROM normalized_transaction
                    WHERE tenant_id = :tenant_id
                    AND psp_connection_id = :psp_conn
                    AND psp_transaction_id = :psp_txn_id
                    AND event_type = :event_type
                """),
                {
                    'tenant_id': str(normalized.tenant_id),
                    'psp_conn': normalized.psp_connection_id,
                    'psp_txn_id': normalized.psp_transaction_id,
                    'event_type': normalized.event_type.value
                }
            ).fetchone()
            
            if existing:
                logger.info(f"Transaction already exists: {existing[0]}")
                # Return existing (or update if needed)
                return normalized
            
            # Insert new transaction
            session.execute(
                text("""
                    INSERT INTO normalized_transaction (
                        transaction_id, tenant_id, brand_id, entity_id,
                        psp_connection_id, event_type, event_timestamp, transaction_date,
                        amount_value, amount_currency, amount_original_currency,
                        amount_fx_rate, amount_fx_rate_source, amount_fx_rate_date,
                        psp_transaction_id, psp_payment_id, psp_settlement_id, psp_batch_id,
                        customer_id, player_id, game_session_id,
                        psp_fee, fx_fee, net_amount,
                        status, reconciliation_status,
                        source_type, source_idempotency_key,
                        source_raw_event_id, source_raw_event_s3_path,
                        metadata, version, schema_version
                    ) VALUES (
                        :transaction_id, :tenant_id, :brand_id, :entity_id,
                        :psp_connection_id, :event_type, :event_timestamp, :transaction_date,
                        :amount_value, :amount_currency, :amount_original_currency,
                        :amount_fx_rate, :amount_fx_rate_source, :amount_fx_rate_date,
                        :psp_transaction_id, :psp_payment_id, :psp_settlement_id, :psp_batch_id,
                        :customer_id, :player_id, :game_session_id,
                        :psp_fee, :fx_fee, :net_amount,
                        :status, :reconciliation_status,
                        :source_type, :source_idempotency_key,
                        :source_raw_event_id, :source_raw_event_s3_path,
                        :metadata, :version, :schema_version
                    )
                    ON CONFLICT (tenant_id, psp_connection_id, psp_transaction_id, event_type)
                    DO NOTHING
                """),
                {
                    'transaction_id': str(normalized.transaction_id),
                    'tenant_id': str(normalized.tenant_id),
                    'brand_id': str(normalized.brand_id),
                    'entity_id': str(normalized.entity_id),
                    'psp_connection_id': normalized.psp_connection_id,
                    'event_type': normalized.event_type.value,
                    'event_timestamp': normalized.event_timestamp,
                    'transaction_date': normalized.transaction_date,
                    'amount_value': normalized.amount_value,
                    'amount_currency': normalized.amount_currency,
                    'amount_original_currency': normalized.amount_original_currency,
                    'amount_fx_rate': float(normalized.amount_fx_rate) if normalized.amount_fx_rate else None,
                    'amount_fx_rate_source': normalized.amount_fx_rate_source,
                    'amount_fx_rate_date': normalized.amount_fx_rate_date,
                    'psp_transaction_id': normalized.psp_transaction_id,
                    'psp_payment_id': normalized.psp_payment_id,
                    'psp_settlement_id': normalized.psp_settlement_id,
                    'psp_batch_id': normalized.psp_batch_id,
                    'customer_id': normalized.customer_id,
                    'player_id': normalized.player_id,
                    'game_session_id': normalized.game_session_id,
                    'psp_fee': normalized.psp_fee,
                    'fx_fee': normalized.fx_fee,
                    'net_amount': normalized.net_amount,
                    'status': normalized.status.value,
                    'reconciliation_status': normalized.reconciliation_status.value,
                    'source_type': normalized.source_type,
                    'source_idempotency_key': normalized.source_idempotency_key,
                    'source_raw_event_id': str(normalized.source_raw_event_id) if normalized.source_raw_event_id else None,
                    'source_raw_event_s3_path': normalized.source_raw_event_s3_path,
                    'metadata': json.dumps(normalized.metadata),
                    'version': normalized.version,
                    'schema_version': normalized.schema_version
                }
            )
            session.commit()
        
        return normalized
    
    async def _publish_to_matching(self, normalized: NormalizedTransaction):
        """Publish normalized transaction to Kinesis for matching"""
        record = {
            'transaction_id': str(normalized.transaction_id),
            'tenant_id': str(normalized.tenant_id),
            'psp_connection_id': normalized.psp_connection_id,
            'event_type': normalized.event_type.value,
            'transaction_date': normalized.transaction_date.isoformat(),
            'amount_value': normalized.amount_value,
            'amount_currency': normalized.amount_currency,
            'psp_transaction_id': normalized.psp_transaction_id,
            'psp_payment_id': normalized.psp_payment_id,
            'psp_settlement_id': normalized.psp_settlement_id,
            'reconciliation_status': normalized.reconciliation_status.value
        }
        
        kinesis_client.put_record(
            StreamName=self.kinesis_stream,
            Data=json.dumps(record, default=str),
            PartitionKey=str(normalized.tenant_id)
        )
    
    def _map_event_type(self, psp_event_type: str) -> EventType:
        """Map PSP event type to canonical EventType"""
        # Default mapping - should be overridden per PSP
        mapping = {
            'DEPOSIT': EventType.DEPOSIT,
            'WITHDRAWAL': EventType.WITHDRAWAL,
            'REFUND': EventType.REFUND,
            'CHARGEBACK': EventType.CHARGEBACK,
            'SETTLEMENT': EventType.DEPOSIT,  # Settlement is a type of deposit
        }
        return mapping.get(psp_event_type.upper(), EventType.DEPOSIT)
    
    def _map_status(self, psp_status: str) -> TransactionStatus:
        """Map PSP status to canonical TransactionStatus"""
        mapping = {
            'completed': TransactionStatus.COMPLETED,
            'succeeded': TransactionStatus.COMPLETED,
            'pending': TransactionStatus.PENDING,
            'failed': TransactionStatus.FAILED,
            'cancelled': TransactionStatus.CANCELLED,
        }
        return mapping.get(psp_status.lower(), TransactionStatus.PENDING)
    
    def _parse_timestamp(self, timestamp_str: Any) -> datetime:
        """Parse timestamp string to datetime"""
        if isinstance(timestamp_str, datetime):
            return timestamp_str
        if isinstance(timestamp_str, (int, float)):
            return datetime.fromtimestamp(timestamp_str)
        # Try ISO format
        return datetime.fromisoformat(str(timestamp_str).replace('Z', '+00:00'))
    
    def _parse_date(self, date_value: Any) -> date:
        """Parse date value to date"""
        if isinstance(date_value, date):
            return date_value
        if isinstance(date_value, datetime):
            return date_value.date()
        return datetime.fromisoformat(str(date_value)).date()
    
    async def _get_entity_brand(
        self,
        tenant_id: UUID,
        psp_connection_id: str
    ) -> tuple[UUID, UUID]:
        """Get entity_id and brand_id from PSP connection"""
        with self.SessionLocal() as session:
            result = session.execute(
                text("""
                    SELECT entity_id, e.brand_id
                    FROM psp_connection pc
                    JOIN entity e ON pc.entity_id = e.entity_id
                    WHERE pc.psp_connection_id = :psp_conn
                    AND pc.tenant_id = :tenant_id
                """),
                {
                    'psp_conn': psp_connection_id,
                    'tenant_id': str(tenant_id)
                }
            ).fetchone()
            
            if result:
                return UUID(result[0]), UUID(result[1])
            else:
                raise ValueError(f"PSP connection not found: {psp_connection_id}")
    
    async def _get_psp_config(
        self,
        tenant_id: UUID,
        psp_connection_id: str
    ) -> Dict[str, Any]:
        """Get PSP connection configuration"""
        with self.SessionLocal() as session:
            result = session.execute(
                text("""
                    SELECT entity_id, parser_version, config
                    FROM psp_connection
                    WHERE psp_connection_id = :psp_conn
                    AND tenant_id = :tenant_id
                """),
                {
                    'psp_conn': psp_connection_id,
                    'tenant_id': str(tenant_id)
                }
            ).fetchone()
            
            if result:
                # Get entity base currency
                entity_result = session.execute(
                    text("SELECT base_currency FROM entity WHERE entity_id = :entity_id"),
                    {'entity_id': str(result[0])}
                ).fetchone()
                
                return {
                    'entity_id': result[0],
                    'parser_version': result[1],
                    'config': json.loads(result[2]) if result[2] else {},
                    'base_currency': entity_result[0] if entity_result else None
                }
            else:
                return {}


