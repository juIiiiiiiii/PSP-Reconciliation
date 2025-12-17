"""
Stripe Parser - Parses Stripe webhooks and settlement files
"""

import csv
import io
import json
from typing import List, Dict, Any
from datetime import datetime

from services.ingestion.parsers.base import BaseParser
from shared.models.transaction import EventType


class StripeParser(BaseParser):
    """Parser for Stripe events and settlement files"""
    
    def __init__(self, version: str = "v2.1"):
        super().__init__(version)
        self.psp_name = "stripe"
    
    async def parse(
        self,
        content: bytes,
        file_format: str
    ) -> List[Dict[str, Any]]:
        """Parse Stripe content"""
        if file_format == 'JSON':
            return await self._parse_json(content)
        elif file_format == 'CSV':
            return await self._parse_csv(content)
        else:
            raise ValueError(f"Unsupported format for Stripe: {file_format}")
    
    async def _parse_json(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse Stripe webhook JSON"""
        data = json.loads(content)
        
        # Stripe webhook format
        if 'type' in data and 'data' in data:
            event_type = data['type']
            event_data = data['data']['object']
            
            return [{
                'psp_event_id': data.get('id'),
                'psp_event_type': event_type,
                'event_type': self.normalize_event_type(event_type),
                'data': event_data,
                'created': data.get('created'),
                'livemode': data.get('livemode', False)
            }]
        else:
            # Array of events
            events = []
            for item in data:
                events.append({
                    'psp_event_id': item.get('id'),
                    'psp_event_type': item.get('type'),
                    'event_type': self.normalize_event_type(item.get('type', '')),
                    'data': item.get('data', {}).get('object', {}),
                    'created': item.get('created')
                })
            return events
    
    async def _parse_csv(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse Stripe settlement CSV"""
        text = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(text))
        
        events = []
        for row in reader:
            # Map Stripe CSV columns to normalized format
            event = {
                'psp_transaction_id': row.get('id'),
                'psp_payment_id': row.get('payment_intent'),
                'amount': int(float(row.get('amount', 0)) * 100),  # Convert to cents
                'currency': row.get('currency', 'USD').upper(),
                'status': row.get('status'),
                'created': row.get('created'),
                'fee': int(float(row.get('fee', 0)) * 100),
                'net': int(float(row.get('net', 0)) * 100),
                'event_type': 'SETTLEMENT'
            }
            events.append(event)
        
        return events
    
    def normalize_event_type(self, psp_event_type: str) -> str:
        """Map Stripe event types to canonical types"""
        mapping = {
            'payment_intent.succeeded': EventType.DEPOSIT,
            'charge.succeeded': EventType.DEPOSIT,
            'charge.refunded': EventType.REFUND,
            'charge.dispute.created': EventType.CHARGEBACK,
            'charge.dispute.closed': EventType.CHARGEBACK_REVERSAL,
            'payout.paid': EventType.SETTLEMENT,
        }
        
        return mapping.get(psp_event_type, psp_event_type.upper())
    
    def validate(self, event: Dict[str, Any]) -> bool:
        """Validate Stripe event"""
        required_fields = ['psp_event_id', 'event_type']
        return all(field in event for field in required_fields)


